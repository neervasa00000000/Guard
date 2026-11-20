import Foundation
import Vision
import ImageIO
import CoreGraphics

struct Line: Codable {
    var text: String
    var confidence: Float
    var x: Double
    var y: Double
    var w: Double
    var h: Double
}

struct Page: Codable {
    var path: String
    var width: Int
    var height: Int
    var lines: [Line]
    var error: String?
}

func recognize(_ path: String) -> Page {
    let url = URL(fileURLWithPath: path)
    guard let src = CGImageSourceCreateWithURL(url as CFURL, nil),
          let cg = CGImageSourceCreateImageAtIndex(src, 0, nil) else {
        return Page(path: path, width: 0, height: 0, lines: [], error: "unreadable")
    }
    let request = VNRecognizeTextRequest()
    request.recognitionLevel = .accurate
    request.usesLanguageCorrection = false
    request.automaticallyDetectsLanguage = true
    let handler = VNImageRequestHandler(cgImage: cg, options: [:])
    do {
        try handler.perform([request])
    } catch {
        return Page(path: path, width: cg.width, height: cg.height, lines: [], error: String(describing: error))
    }
    let width = Double(cg.width)
    let height = Double(cg.height)
    var lines: [Line] = []
    for observation in request.results ?? [] {
        guard let candidate = observation.topCandidates(1).first else { continue }
        let box = observation.boundingBox
        let w = box.size.width * width
        let h = box.size.height * height
        let x = box.origin.x * width
        let y = (1.0 - box.origin.y) * height - h
        lines.append(Line(text: candidate.string, confidence: candidate.confidence, x: x, y: y, w: w, h: h))
    }
    return Page(path: path, width: cg.width, height: cg.height, lines: lines, error: nil)
}

let encoder = JSONEncoder()
while let line = readLine() {
    let path = line.trimmingCharacters(in: .whitespacesAndNewlines)
    if path.isEmpty { continue }
    let page = recognize(path)
    if let data = try? encoder.encode(page), let text = String(data: data, encoding: .utf8) {
        print(text)
        fflush(stdout)
    }
}
