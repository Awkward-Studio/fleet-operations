import 'package:google_mlkit_text_recognition/google_mlkit_text_recognition.dart';

class OdometerOcrResult {
  const OdometerOcrResult({
    required this.readingKm,
    required this.rawText,
    required this.candidates,
  });

  final int? readingKm;
  final String rawText;
  final List<int> candidates;

  bool get hasReading => readingKm != null;
}

class OdometerOcrService {
  const OdometerOcrService._();

  static Future<OdometerOcrResult> readOdometerKm(
    String imagePath, {
    int? minimumKm,
  }) async {
    final recognizer = TextRecognizer(script: TextRecognitionScript.latin);
    try {
      final inputImage = InputImage.fromFilePath(imagePath);
      final recognizedText = await recognizer.processImage(inputImage);
      final candidates = _extractCandidates(recognizedText.text, minimumKm);

      return OdometerOcrResult(
        readingKm: candidates.isEmpty ? null : candidates.first,
        rawText: recognizedText.text,
        candidates: candidates,
      );
    } finally {
      await recognizer.close();
    }
  }

  static List<int> _extractCandidates(String text, int? minimumKm) {
    final normalized = text
        .replaceAll(RegExp(r'[OoQD]'), '0')
        .replaceAll(RegExp(r'[Il|]'), '1')
        .replaceAll(RegExp(r'[Ss]'), '5')
        .replaceAll(RegExp(r'[Bb]'), '8');
    final matches =
        RegExp(r'[0-9][0-9\s,\.]{2,}[0-9]').allMatches(normalized);
    final values = <int>{};

    for (final match in matches) {
      final token = match.group(0);
      if (token == null) continue;

      final withoutDecimal = token.split('.').first;
      final digits = withoutDecimal.replaceAll(RegExp(r'[^0-9]'), '');
      if (digits.length < 4 || digits.length > 7) continue;

      final value = int.tryParse(digits);
      if (value == null || value <= 0 || value > 9999999) continue;
      if (minimumKm != null && value < minimumKm) continue;
      values.add(value);
    }

    final sorted = values.toList();
    sorted.sort((a, b) {
      if (minimumKm == null) return b.compareTo(a);
      return (a - minimumKm).compareTo(b - minimumKm);
    });
    return sorted;
  }
}
