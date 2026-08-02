import 'dart:ui';

import 'package:flutter/foundation.dart';
import 'package:google_mlkit_text_recognition/google_mlkit_text_recognition.dart';

// ---------------------------------------------------------------------------
// Result
// ---------------------------------------------------------------------------

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

// ---------------------------------------------------------------------------
// Internal geometry helpers
// ---------------------------------------------------------------------------

/// A spatially-contiguous cluster of [TextElement]s that sit on the same
/// horizontal line and whose bounding boxes are close enough to be considered
/// part of the same printed number.
///
/// NOTE: O(n²) row-grouping below is intentional — odometer frames contain
/// only a handful of elements, so readability is preferred over raw speed.
/// Do not use this path for dense-document OCR.
class _ElementRun {
  _ElementRun(this.elements);

  final List<TextElement> elements;

  Rect get bounds => elements
      .map((e) => e.boundingBox)
      .reduce((a, b) => _expandToInclude(a, b));

  static Rect _expandToInclude(Rect a, Rect b) => Rect.fromLTRB(
        a.left < b.left ? a.left : b.left,
        a.top < b.top ? a.top : b.top,
        a.right > b.right ? a.right : b.right,
        a.bottom > b.bottom ? a.bottom : b.bottom,
      );
}

// ---------------------------------------------------------------------------
// Service
// ---------------------------------------------------------------------------

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

      debugPrint('=== RAW OCR TEXT ===');
      debugPrint(recognizedText.text);
      debugPrint('===================');

      // ── Element-based path (primary) ──────────────────────────────────────
      final elementCandidates =
          _extractCandidatesFromElements(recognizedText, minimumKm);

      // ── Text-based path (fallback / second vote) ──────────────────────────
      final textCandidates = <int>{};
      for (final block in recognizedText.blocks) {
        textCandidates.addAll(_extractCandidatesFromText(block.text, minimumKm));
        for (final line in block.lines) {
          textCandidates
              .addAll(_extractCandidatesFromText(line.text, minimumKm));
        }
      }
      textCandidates
          .addAll(_extractCandidatesFromText(recognizedText.text, minimumKm));

      debugPrint(
          'Element-based candidates : $elementCandidates');
      debugPrint(
          'Text-based candidates    : ${textCandidates.toList()}');

      // ── Combine & rank ────────────────────────────────────────────────────
      // Values that appear in both paths get double-weighted by being inserted
      // twice before sorting — they will naturally float to the top.
      final combined = <int>[
        ...elementCandidates,
        for (final v in textCandidates)
          if (elementCandidates.contains(v)) v, // double-weight agreements
        ...textCandidates,
      ];

      // Deduplicate while preserving order so the double-weighted entries
      // still get counted once in the final unique list.
      final seen = <int>{};
      final candidates = <int>[];
      for (final v in combined) {
        if (seen.add(v)) candidates.add(v);
      }

      // Sort: if we have a reference value, prefer the closest; otherwise
      // prefer the largest (highest km reading is most likely the odometer).
      candidates.sort((a, b) {
        if (minimumKm == null) return b.compareTo(a);
        return (a - minimumKm).abs().compareTo((b - minimumKm).abs());
      });

      debugPrint('Final ranked candidates  : $candidates');

      return OdometerOcrResult(
        readingKm: candidates.isEmpty ? null : candidates.first,
        rawText: recognizedText.text,
        candidates: candidates,
      );
    } finally {
      await recognizer.close();
    }
  }

  // ── Element-level geometry-aware extraction ──────────────────────────────

  static List<int> _extractCandidatesFromElements(
    RecognizedText recognizedText,
    int? minimumKm,
  ) {
    // 1. Flatten all elements, skip any without a bounding box.
    final elements = <TextElement>[
      for (final block in recognizedText.blocks)
        for (final line in block.lines)
          for (final element in line.elements) element,
    ];

    if (elements.isEmpty) return [];

    final avgHeight = elements
            .map((e) => e.boundingBox.height)
            .reduce((a, b) => a + b) /
        elements.length;

    debugPrint('--- Element OCR: ${elements.length} elements, '
        'avgHeight=${avgHeight.toStringAsFixed(1)}px ---');

    // 2. Group into rows by vertical-centre proximity.
    //    Tolerance = 50 % of the average element height so that slightly
    //    tilted or scaled digits still land in the same row.
    final rowTolerance = avgHeight * 0.5;
    final rows = <List<TextElement>>[];

    for (final el in elements) {
      final centerY = el.boundingBox.center.dy;

      List<TextElement>? target;
      for (final row in rows) {
        final rowCenterY = row
                .map((e) => e.boundingBox.center.dy)
                .reduce((a, b) => a + b) /
            row.length;
        if ((centerY - rowCenterY).abs() < rowTolerance) {
          target = row;
          break;
        }
      }
      if (target == null) {
        target = <TextElement>[];
        rows.add(target);
      }
      target.add(el);
    }

    debugPrint('--- Element OCR: grouped into ${rows.length} row(s) ---');

    final candidates = <int>[];
    // Gap threshold: elements within 60 % of avgHeight of each other
    // are considered part of the same printed number.
    final gapThreshold = avgHeight * 0.6;

    for (var ri = 0; ri < rows.length; ri++) {
      final row = rows[ri];

      // 3. Sort left-to-right within the row.
      row.sort((a, b) =>
          a.boundingBox.left.compareTo(b.boundingBox.left));

      // 4. Chain into runs by horizontal gap.
      final runs = <_ElementRun>[];
      var current = <TextElement>[];

      for (var i = 0; i < row.length; i++) {
        if (current.isEmpty) {
          current.add(row[i]);
          continue;
        }
        final prevRight = current.last.boundingBox.right;
        final gap = row[i].boundingBox.left - prevRight;
        if (gap <= gapThreshold) {
          current.add(row[i]);
        } else {
          runs.add(_ElementRun(List.of(current)));
          current = [row[i]];
        }
      }
      if (current.isNotEmpty) runs.add(_ElementRun(List.of(current)));

      debugPrint('  Row $ri: ${row.length} elements → ${runs.length} run(s)');

      // 5-6. Per run: normalize each element → digits, drop pure-noise
      //      elements (those that yield no digits), concatenate the rest.
      for (var rj = 0; rj < runs.length; rj++) {
        final run = runs[rj];

        final perElement = run.elements
            .map((e) => (raw: e.text, digits: _normalizeToDigits(e.text)))
            .toList();

        final digits = perElement.map((e) => e.digits).join();

        debugPrint('    Run $rj: '
            '${perElement.map((e) => '"${e.raw}"→"${e.digits}"').join(', ')} '
            '→ "$digits"');

        if (digits.length < 4 || digits.length > 7) {
          debugPrint('      Skipped (length ${digits.length} out of 4–7)');
          continue;
        }

        final value = int.tryParse(digits);
        if (value == null || value <= 0 || value > 9_999_999) {
          debugPrint('      Skipped (invalid value)');
          continue;
        }
        if (minimumKm != null && value < minimumKm) {
          debugPrint('      Skipped (below minimumKm $minimumKm)');
          continue;
        }

        debugPrint('      ✓ Accepted: $value');
        candidates.add(value);
      }
    }

    // Deduplicate while preserving first-seen order.
    final seen = <int>{};
    return candidates.where(seen.add).toList();
  }

  // ── Text-level extraction (kept as fallback) ─────────────────────────────

  static List<int> _extractCandidatesFromText(String text, int? minimumKm) {
    final normalized = text
        .replaceAll(RegExp(r'[OoQqDd]'), '0')
        .replaceAll(RegExp(r'[Il|!]'), '1')
        .replaceAll(RegExp(r'[Ss]'), '5')
        .replaceAll(RegExp(r'[Bb]'), '8')
        .replaceAll(RegExp(r'[Zz]'), '2')
        // Bridge a short run of OCR noise sitting directly between two
        // digits (dashboard glare, needle, divider bar, etc.) so a leading
        // digit doesn't get isolated into its own sub-4-char fragment and
        // discarded.
        .replaceAllMapped(
          RegExp(r'(\d)[^\d\s,.]{1,2}(\d)'),
          (m) => '${m.group(1)}${m.group(2)}',
        );

    final values = <int>{};
    final matches = RegExp(r'[\d\s,.]{4,}').allMatches(normalized);

    for (final match in matches) {
      final token = match.group(0);
      if (token == null) continue;

      final digits = token.replaceAll(RegExp(r'\D'), '');
      if (digits.length < 4 || digits.length > 7) continue;

      final value = int.tryParse(digits);
      if (value == null) continue;
      if (value <= 0 || value > 9_999_999) continue;
      if (minimumKm != null && value < minimumKm) continue;

      values.add(value);
    }

    return values.toList();
  }

  // ── Digit normalisation ───────────────────────────────────────────────────

  /// Applies common OCR glyph-substitution corrections and strips all
  /// non-digit characters, returning only the digit string.
  /// Pure noise elements (no digits after substitution) return ''.
  static String _normalizeToDigits(String text) {
    final mapped = text
        .replaceAll(RegExp(r'[OoQqDd]'), '0')
        .replaceAll(RegExp(r'[Il|!]'), '1')
        .replaceAll(RegExp(r'[Ss]'), '5')
        .replaceAll(RegExp(r'[Bb]'), '8')
        .replaceAll(RegExp(r'[Zz]'), '2');
    return mapped.replaceAll(RegExp(r'\D'), '');
  }
}
