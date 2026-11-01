import SwiftUI
import AppKit
import UniformTypeIdentifiers

struct Theme: Decodable, Identifiable {
    let id: String
    let name: String
    let description: String
    let font: String
    let weight: Int
    let row_height: Int
    let icons: String
    let build_status: String?
    var isBuildable: Bool { build_status != "blocked" }
    func detail(screenHeight: Int = 128) -> String {
        if id == "enlarge" { return "Inter Tight Semibold 13px · \((screenHeight - 19) / row_height) rows · Original icons" }
        let family = font == "roboto" ? "Roboto Condensed Bold" : (weight >= 500 ? "Inter Medium" : "Inter Regular")
        return "\(family) · \((screenHeight - 19) / row_height) rows · Original icons"
    }
}

struct FirmwareDevice: Decodable {
    let id: String
    let display_name: String
    let firmware_version: String
    let lcd_width: Int
    let lcd_height: Int
    let preview_style: String
    let menu_counts: [String:Int]?
}

enum PreviewScreen: String, CaseIterable, Identifiable {
    case main, music, settings, playing
    var id: String { rawValue }
    var title: String {
        switch self { case .main: return "Main Menu"; case .music: return "Music"; case .settings: return "Settings"; case .playing: return "Now Playing" }
    }
}

final class BuilderModel: ObservableObject {
    @Published var themes: [Theme] = []
    @Published var selected = "clear"
    @Published var screen: PreviewScreen = .main
    @Published var compareOriginal = false
    @Published var rowOffset = 0
    @Published var source: URL?
    @Published var preview: NSImage?
    @Published var device: FirmwareDevice?
    @Published var busy = false
    @Published var status = "Choose original monochrome iPod firmware to get started."
    @Published var error: String?
    @Published var lastExport: URL?
    private var generation = 0
    let resources: URL
    let engine: URL

    init() {
        resources = Bundle.main.resourceURL ?? URL(fileURLWithPath: FileManager.default.currentDirectoryPath)
        engine = resources.deletingLastPathComponent().appendingPathComponent("Helpers/PodThemerEngine.app/Contents/MacOS/PodThemerEngine")
        if let data = try? Data(contentsOf: resources.appendingPathComponent("themes.json")), let loaded = try? JSONDecoder().decode([Theme].self, from: data) { themes = loaded }
        let args = ProcessInfo.processInfo.arguments
        if let index = args.firstIndex(of: "--input"), index + 1 < args.count { source = URL(fileURLWithPath: args[index + 1]) }
    }

    var theme: Theme? { themes.first(where: { $0.id == selected }) }
    var canBuild: Bool { source != nil && device != nil && preview != nil && !busy && theme?.isBuildable == true }

    func scrollRows(_ delta: Int) {
        let count = device?.menu_counts?[screen.rawValue] ?? (screen == .main ? 6 : (screen == .music ? 8 : (screen == .settings ? 15 : 0)))
        let height = compareOriginal ? 18 : (theme?.row_height ?? 24)
        let available = (device?.lcd_height ?? 128) - 19
        rowOffset = min(max(0, count - available / height), max(0, rowOffset + delta))
    }

    func chooseSource() {
        let panel = NSOpenPanel()
        panel.title = "Choose original iPod firmware"
        panel.message = "Use original firmware for iPod generations 1–4 or iPod mini generations 1–2."
        panel.canChooseDirectories = false
        panel.allowsMultipleSelection = false
        if panel.runModal() == .OK, let url = panel.url { source = url; preview = nil; device = nil; lastExport = nil; requestPreview() }
    }

    func runEngine(_ arguments: [String]) throws -> [String: Any] {
        let process = Process()
        process.executableURL = engine
        process.arguments = arguments
        let out = Pipe(), err = Pipe()
        process.standardOutput = out; process.standardError = err
        try process.run()
        let output = out.fileHandleForReading.readDataToEndOfFile()
        process.waitUntilExit()
        let errorData = err.fileHandleForReading.readDataToEndOfFile()
        let object = (try? JSONSerialization.jsonObject(with: output)) as? [String: Any]
        if process.terminationStatus != 0 {
            let details = object?["error"] as? String ?? String(data: errorData, encoding: .utf8) ?? "The builder could not run."
            throw NSError(domain: "PodThemer", code: 2, userInfo: [NSLocalizedDescriptionKey: details])
        }
        guard let value = object, value["ok"] as? Bool == true else { throw NSError(domain: "PodThemer", code: 3, userInfo: [NSLocalizedDescriptionKey: "The firmware engine returned an invalid response."]) }
        return value
    }

    func requestPreview() {
        guard let source = source else { return }
        generation += 1
        let ticket = generation, themeID = compareOriginal ? "original" : selected, screenID = screen.rawValue, offset = rowOffset
        busy = true; error = nil; status = "Rendering \(theme?.name ?? "theme")…"
        let url = FileManager.default.temporaryDirectory.appendingPathComponent("podtheme-\(UUID().uuidString).png")
        DispatchQueue.global(qos: .userInitiated).async {
            do {
                let response = try self.runEngine(["--input", source.path, "--theme", themeID, "--screen", screenID, "--offset", String(offset), "--preview", url.path])
                let image = NSImage(contentsOf: url)
                guard let value = response["device"], let data = try? JSONSerialization.data(withJSONObject: value),
                      let identified = try? JSONDecoder().decode(FirmwareDevice.self, from: data),
                      ["click-wheel-4g", "click-wheel-mini", "touch-wheel-3g", "scroll-wheel-1g2g"].contains(identified.preview_style), [160,138].contains(identified.lcd_width), [128,110].contains(identified.lcd_height) else {
                    throw NSError(domain: "PodThemer", code: 4, userInfo: [NSLocalizedDescriptionKey: "No supported device preview matches this firmware."])
                }
                try? FileManager.default.removeItem(at: url)
                DispatchQueue.main.async {
                    guard ticket == self.generation else { return }
                    self.preview = image; self.device = identified; self.busy = false
                    self.status = "\(response["theme"] as? String ?? "Theme") preview ready. Original firmware verified."
                }
            } catch {
                try? FileManager.default.removeItem(at: url)
                DispatchQueue.main.async {
                    guard ticket == self.generation else { return }
                    self.preview = nil; self.device = nil; self.busy = false; self.status = "Choose a supported original firmware file."
                    self.error = error.localizedDescription
                }
            }
        }
    }

    func export() {
        guard canBuild, let source = source else { return }
        let panel = NSSavePanel()
        panel.title = "Build themed firmware"
        panel.message = "Saves a new IPSW, a validation report, and a preview. Installing this file is a separate restore step."
        panel.nameFieldStringValue = "\(device?.id ?? "iPod")-\(theme?.name ?? selected)-EXPERIMENTAL.ipsw"
        panel.canCreateDirectories = true
        guard panel.runModal() == .OK, let output = panel.url else { return }
        let themeID = selected
        busy = true; error = nil; status = "Building and verifying firmware…"
        DispatchQueue.global(qos: .userInitiated).async {
            do {
                _ = try self.runEngine(["--input", source.path, "--theme", themeID, "--output", output.path])
                DispatchQueue.main.async { self.busy = false; self.lastExport = output; self.status = "Built and verified \(output.lastPathComponent)." }
            } catch {
                DispatchQueue.main.async { self.busy = false; self.error = error.localizedDescription; self.status = "Firmware was not exported." }
            }
        }
    }
}

struct ThemeCard: View {
    let theme: Theme
    let selected: Bool
    let action: () -> Void
    var body: some View {
        Button(action: action) {
            HStack(alignment: .top, spacing: 12) {
                Image(systemName: selected ? "checkmark.circle.fill" : "circle")
                    .font(.system(size: 19)).foregroundStyle(selected ? Color.primary : Color.secondary)
                    .padding(.top, 2)
                VStack(alignment: .leading, spacing: 5) {
                    Text(theme.name).font(.system(size: 16, weight: .semibold))
                    Text(theme.description).font(.system(size: 12)).foregroundStyle(.secondary).fixedSize(horizontal: false, vertical: true)
                }
                Spacer(minLength: 0)
                Text("Aa").font(.system(size: 25, weight: theme.id == "focus" ? .bold : .medium, design: .default)).foregroundStyle(.secondary)
            }
            .padding(14).frame(maxWidth: .infinity, alignment: .leading)
            .background(selected ? Color.primary.opacity(0.07) : Color(nsColor: .controlBackgroundColor))
            .clipShape(RoundedRectangle(cornerRadius: 13))
            .overlay(RoundedRectangle(cornerRadius: 13).stroke(selected ? Color.primary.opacity(0.45) : Color.primary.opacity(0.09), lineWidth: 1))
            .contentShape(RoundedRectangle(cornerRadius: 13))
        }.buttonStyle(.plain).accessibilityLabel("\(theme.name) theme").accessibilityAddTraits(selected ? .isSelected : [])
    }
}

// Original vector device illustrations, referenced against Apple's model-identification photos.
// Geometry is independent of firmware rendering: the LCD remains an unfiltered pixel image.
struct DevicePreview: View {
    @ObservedObject var model: BuilderModel
    var mini: Bool { model.device?.preview_style == "click-wheel-mini" }
    var third: Bool { model.device?.preview_style == "touch-wheel-3g" }
    var early: Bool { model.device?.preview_style == "scroll-wheel-1g2g" }
    var width: CGFloat { mini ? 276 : 320 }
    var height: CGFloat { mini ? 497 : 538 }
    var radius: CGFloat { mini ? 5 : (early ? 27 : 30) }
    var screenWidth: CGFloat { CGFloat(model.device?.lcd_width ?? 160) * 1.4 }
    var screenHeight: CGFloat { CGFloat(model.device?.lcd_height ?? 128) * 1.4 }
    let ivory = Color(red: 0.96, green: 0.965, blue: 0.955)

    func control(_ symbol: String, label: String, x: CGFloat, y: CGFloat, menu: Bool = false, action: @escaping () -> Void) -> some View {
        Button(action: action) {
            Group {
                if menu { Text(early ? "menu" : "MENU").font(.system(size: early ? 13 : 11, weight: .semibold)) }
                else { Image(systemName: symbol).font(.system(size: 13, weight: .semibold)) }
            }.frame(width: 46, height: 34).contentShape(Rectangle())
        }.buttonStyle(.plain).foregroundStyle(Color(white: early ? 0.57 : 0.43))
            .accessibilityLabel(label).position(x: x, y: y)
    }

    var casework: some View {
        ZStack {
            RoundedRectangle(cornerRadius: radius).fill(LinearGradient(stops: [
                .init(color: Color(white: 0.55), location: 0), .init(color: .white, location: 0.015),
                .init(color: Color(white: 0.77), location: 0.035), .init(color: .white, location: 0.075),
                .init(color: Color(white: 0.9), location: 0.94), .init(color: Color(white: 0.54), location: 1)
            ], startPoint: .leading, endPoint: .trailing))
            if mini {
                RoundedRectangle(cornerRadius: radius).fill(LinearGradient(stops: [
                    .init(color: Color(white: 0.42), location: 0), .init(color: Color(white: 0.71), location: 0.045),
                    .init(color: Color(white: 0.88), location: 0.13), .init(color: Color(white: 0.83), location: 0.5),
                    .init(color: Color(white: 0.79), location: 0.87), .init(color: Color(white: 0.52), location: 1)
                ], startPoint: .leading, endPoint: .trailing))
                // Subtle drawn grain, with no bundled product photographs.
                Canvas { context, size in
                    for y in stride(from: 1.0, to: size.height, by: 2) {
                        var line = Path(); line.move(to: CGPoint(x: 8, y: y)); line.addLine(to: CGPoint(x: size.width - 8, y: y))
                        context.stroke(line, with: .color(.white.opacity(0.065)), lineWidth: 0.5)
                    }
                }.clipShape(RoundedRectangle(cornerRadius: radius))
            } else {
                RoundedRectangle(cornerRadius: radius - 2).fill(LinearGradient(colors: [.white, ivory, Color(white: 0.92)], startPoint: .topLeading, endPoint: .bottomTrailing)).padding(early ? 4 : 3)
                RoundedRectangle(cornerRadius: radius - 4).stroke(.white.opacity(0.85), lineWidth: 2).padding(6)
            }
            RoundedRectangle(cornerRadius: radius).stroke(Color.black.opacity(0.2), lineWidth: 0.7)
        }
    }

    var wheel: some View {
        let diameter: CGFloat = early ? 270 : (third ? 216 : (mini ? 214 : 216))
        let center = diameter / 2
        return ZStack {
            Circle().fill(LinearGradient(colors: [Color(white: early || third ? 0.98 : (mini ? 0.96 : 0.85)), Color(white: early || third ? 0.9 : (mini ? 0.91 : 0.81))], startPoint: .topLeading, endPoint: .bottomTrailing))
                .overlay(Circle().stroke(Color.black.opacity(0.18), lineWidth: 1))
                .overlay(Circle().stroke(.white.opacity(0.8), lineWidth: 1).padding(1.5))
            if early {
                // Four discrete outer buttons surround the scroll/touch wheel on Gen 1/2.
                Path { p in
                    for angle in [45.0, 135.0, 225.0, 315.0] {
                        let a = angle * .pi / 180
                        p.move(to: CGPoint(x: center + cos(a) * 105, y: center + sin(a) * 105))
                        p.addLine(to: CGPoint(x: center + cos(a) * 134, y: center + sin(a) * 134))
                    }
                }.stroke(Color(white: 0.54), lineWidth: 1)
                Circle().fill(LinearGradient(colors: [.white, Color(white: 0.9)], startPoint: .topLeading, endPoint: .bottomTrailing)).frame(width: 210, height: 210)
                    .overlay(Circle().stroke(Color(white: 0.48), lineWidth: 1.5))
            }
            Circle().fill(LinearGradient(colors: [Color(white: 0.98), Color(white: 0.91)], startPoint: .topLeading, endPoint: .bottomTrailing))
                .frame(width: early ? 76 : 72, height: early ? 76 : 72)
                .overlay(Circle().stroke(Color.black.opacity(0.17), lineWidth: 0.8))
                .overlay(Circle().stroke(.white.opacity(0.9), lineWidth: 1).padding(2))
                .allowsHitTesting(false)
            if !third {
                let inset: CGFloat = early ? 15 : 20
                control("", label: "Main Menu", x: center, y: inset, menu: true) { model.rowOffset = 0; model.screen = .main }
                control("backward.end.fill", label: "Previous menu rows", x: inset, y: center) { model.scrollRows(-1) }
                control("forward.end.fill", label: "Next menu rows", x: diameter - inset, y: center) { model.scrollRows(1) }
                control("playpause.fill", label: "Now Playing", x: center, y: diameter - inset) { model.screen = .playing }
            }
        }.frame(width: diameter, height: diameter)
    }

    func touchButton(_ symbol: String, label: String, menu: Bool = false, action: @escaping () -> Void) -> some View {
        Button(action: action) {
            ZStack {
                Circle().fill(LinearGradient(colors: [Color(white: 0.88), .white], startPoint: .topLeading, endPoint: .bottomTrailing))
                Circle().fill(ivory).padding(3).shadow(color: .white, radius: 1, x: -1, y: -1)
                if menu { Text("MENU").font(.system(size: 9, weight: .bold)) }
                else { Image(systemName: symbol).font(.system(size: 12, weight: .semibold)) }
            }.frame(width: 57, height: 57).contentShape(Circle())
        }.buttonStyle(.plain).foregroundStyle(Color(red: 0.94, green: 0.28, blue: 0.16)).accessibilityLabel(label)
    }

    var body: some View {
        if model.device == nil {
            VStack(spacing: 16) {
                Image(systemName: "doc.badge.magnifyingglass").font(.system(size: 44)).foregroundStyle(.secondary)
                Text("Choose firmware to identify your iPod").font(.headline)
                Text("The preview follows the supported device identified in the firmware.").font(.caption).foregroundStyle(.secondary).multilineTextAlignment(.center)
            }.padding(30).frame(width: 336, height: 490)
        } else {
            ZStack {
                casework
                ZStack {
                    RoundedRectangle(cornerRadius: mini ? 4 : 7).fill(Color(white: 0.4))
                    RoundedRectangle(cornerRadius: mini ? 3 : 5).fill(Color(red: 0.72, green: 0.76, blue: 0.68)).padding(2)
                    if let image = model.preview {
                        Image(nsImage: image).resizable().interpolation(.none).frame(width: screenWidth, height: screenHeight)
                    }
                    RoundedRectangle(cornerRadius: mini ? 3 : 5).stroke(.black.opacity(0.28), lineWidth: 1).padding(2).allowsHitTesting(false)
                }.frame(width: screenWidth + 8, height: screenHeight + 8)
                    .position(x: width / 2, y: (mini ? 35 : 40) + (screenHeight + 8) / 2)
                if third {
                    HStack(spacing: 9) {
                        touchButton("backward.end.fill", label: "Previous menu rows") { model.scrollRows(-1) }
                        touchButton("", label: "Main Menu", menu: true) { model.rowOffset = 0; model.screen = .main }
                        touchButton("playpause.fill", label: "Now Playing") { model.screen = .playing }
                        touchButton("forward.end.fill", label: "Next menu rows") { model.scrollRows(1) }
                    }.position(x: width / 2, y: 271)
                }
                wheel.position(x: width / 2, y: mini ? 340 : (third ? 402 : 385))
            }.frame(width: width, height: height)
                .compositingGroup().shadow(color: .black.opacity(0.16), radius: 12, x: 0, y: 7)
                .padding(.horizontal, 16).padding(.vertical, 12)
        }
    }
}

struct BuilderView: View {
    @StateObject var model = BuilderModel()
    var body: some View {
        VStack(spacing: 0) {
            HStack(alignment: .top, spacing: 30) {
                ScrollView {
                VStack(alignment: .leading, spacing: 20) {
                    VStack(alignment: .leading, spacing: 7) {
                        Text("Pod Themer").font(.system(size: 32, weight: .semibold))
                        Text("Monochrome iPod themes.").font(.system(size: 14)).foregroundStyle(.secondary)
                    }
                    VStack(alignment: .leading, spacing: 10) {
                        Text("1  ORIGINAL FIRMWARE").font(.system(size: 11, weight: .semibold)).foregroundStyle(.secondary)
                        HStack(spacing: 10) {
                            Image(systemName: model.source == nil ? "doc" : "doc.badge.checkmark").font(.system(size: 23)).foregroundStyle(.secondary)
                            VStack(alignment: .leading, spacing: 4) {
                                Text(model.source?.lastPathComponent ?? "Original iPod firmware.ipsw").font(.system(size: 12, weight: .medium)).lineLimit(1).truncationMode(.middle)
                                Text(model.source == nil ? "iPod Gen 1–4 · iPod mini Gen 1–2" : "Original file stays unchanged").font(.system(size: 11)).foregroundStyle(.secondary)
                            }
                            Spacer(minLength: 0)
                            Button(model.source == nil ? "Choose…" : "Change…") { model.chooseSource() }.disabled(model.busy)
                        }.padding(13).background(Color(nsColor: .controlBackgroundColor)).clipShape(RoundedRectangle(cornerRadius: 12))
                    }
                    VStack(alignment: .leading, spacing: 10) {
                        Text("2  CHOOSE A THEME").font(.system(size: 11, weight: .semibold)).foregroundStyle(.secondary)
                        ForEach(model.themes) { theme in ThemeCard(theme: theme, selected: model.selected == theme.id) { model.selected = theme.id }.disabled(model.busy) }
                    }
                    Text("Same menus. Same options. Your choice of typography, spacing and icons.").font(.system(size: 12)).foregroundStyle(.secondary).fixedSize(horizontal: false, vertical: true)
                    Spacer(minLength: 0)
                }
                }.frame(width: 345)
                VStack(spacing: 16) {
                    HStack {
                        VStack(alignment: .leading, spacing: 5) {
                            Text(model.compareOriginal ? "Original" : (model.theme?.name ?? "Preview")).font(.system(size: 22, weight: .semibold))
                            Text(model.compareOriginal ? "Unmodified firmware, for comparison" : (model.theme?.detail(screenHeight: model.device?.lcd_height ?? 128) ?? "Choose firmware")).font(.system(size: 11)).foregroundStyle(.secondary)
                        }
                        Spacer()
                        if model.busy { ProgressView().controlSize(.small) }
                        Toggle("Compare original", isOn: $model.compareOriginal).toggleStyle(.switch).controlSize(.small).fixedSize().disabled(model.busy)
                    }
                    Picker("Preview screen", selection: $model.screen) { ForEach(PreviewScreen.allCases) { screen in Text(screen.title).tag(screen) } }.pickerStyle(.segmented).labelsHidden()
                    GeometryReader { geometry in
                        let deviceHeight: CGFloat = model.device?.preview_style == "click-wheel-mini" ? 521 : 562
                        let scale = min(1, min(geometry.size.height / deviceHeight, geometry.size.width / 368))
                        DevicePreview(model: model).scaleEffect(scale)
                            .frame(width: geometry.size.width, height: geometry.size.height)
                    }
                    if let device = model.device {
                        Text("\(device.display_name) · \(device.lcd_width) × \(device.lcd_height)").font(.system(size: 11, weight: .medium)).foregroundStyle(.secondary)
                    }
                    Text("Firmware-matched LCD preview. Reconstructed screens, not an emulator. Use the wheel arrows to preview more menu rows.").font(.system(size: 11)).foregroundStyle(.secondary).multilineTextAlignment(.center).frame(maxWidth: 380).fixedSize(horizontal: false, vertical: true)
                    Spacer(minLength: 0)
                }.frame(maxWidth: .infinity)
            }.padding(28)
            Divider()
            HStack(spacing: 15) {
                VStack(alignment: .leading, spacing: 4) {
                    Text(model.status).font(.system(size: 12, weight: .medium)).lineLimit(2)
                    Text("Exports firmware only. Installing through Restore is a separate step and erases the iPod.").font(.system(size: 11)).foregroundStyle(.secondary)
                }
                Spacer(minLength: 10)
                if let last = model.lastExport { Button("Show in Finder") { NSWorkspace.shared.activateFileViewerSelecting([last]) } }
                Button("Build \(model.theme?.name ?? "theme") IPSW…") { model.export() }.buttonStyle(.borderedProminent).tint(.primary).disabled(!model.canBuild).keyboardShortcut("s", modifiers: .command)
            }.padding(.horizontal, 28).padding(.vertical, 18)
        }.frame(minWidth: 970, minHeight: 760).background(Color(nsColor: .windowBackgroundColor))
        .onAppear { if model.source != nil { model.requestPreview() } }
        .onChange(of: model.selected) { model.compareOriginal = false; model.rowOffset = 0; model.requestPreview() }
        .onChange(of: model.screen) { model.rowOffset = 0; model.requestPreview() }
        .onChange(of: model.compareOriginal) { model.rowOffset = 0; model.requestPreview() }
        .onChange(of: model.rowOffset) { model.requestPreview() }
        .alert("Couldn’t build this preview", isPresented: Binding(get: { model.error != nil }, set: { if !$0 { model.error = nil } })) { Button("OK") { model.error = nil } } message: { Text(model.error ?? "") }
    }
}

@main struct PodThemerApp: App {
    var body: some Scene {
        WindowGroup("Pod Themer") { BuilderView() }.defaultSize(width: 1000, height: 860)
        .commands { CommandGroup(replacing: .newItem) {} }
    }
}
