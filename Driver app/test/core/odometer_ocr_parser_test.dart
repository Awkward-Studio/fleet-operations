import 'dart:math';

import 'package:flutter_test/flutter_test.dart';

import 'package:driver_app/core/odometer_ocr_parser.dart';

void main() {
  const parser = OdometerOcrParser();

  group('line-preserving parser', () {
    final cases = <({String text, List<int> expected})>[
      (text: 'ODO 541 km', expected: [541]),
      (text: 'TOTAL 000541 KM', expected: [541]),
      (text: '12,345 km', expected: [12345]),
      (text: '1 234 567 km', expected: [1234567]),
      (text: '12345.6 km', expected: [12345]),
      (text: '12S45 km', expected: [12545]),
      (text: 'ODO ISIS km', expected: [1515]),
      (text: 'ISIS', expected: []),
      (text: '1 km', expected: [1]),
      (text: '9999999 km', expected: [9999999]),
      (text: '12 34 541', expected: [12, 34, 541]),
      (text: '12:34', expected: []),
      (text: '12:34 541 km', expected: [541]),
      (text: '11/08/2026', expected: []),
      (text: 'RANGE 541 km', expected: []),
      (text: '80 km/h', expected: []),
      (text: 'AVG 5.4 L/100 km', expected: []),
      (text: 'ODO 541..2', expected: []),
      (text: 'ODO 12,34', expected: []),
      (text: 'ODO DDO 541', expected: [541]),
      (text: 'ODO 12345678', expected: []),
      (text: 'ODO 0000000', expected: []),
    ];

    for (final testCase in cases) {
      test('parses "${testCase.text}"', () {
        expect(
          _values(parser.parse(_document(testCase.text))),
          testCase.expected,
        );
      });
    }

    test('never joins digits across lines or blocks', () {
      final result = parser.parse(
        const OdometerOcrDocumentInput(
          variant: 'normalized',
          blocks: [
            OdometerOcrBlockInput(
              lines: [
                OdometerOcrLineInput(text: '12'),
                OdometerOcrLineInput(text: '345'),
              ],
            ),
            OdometerOcrBlockInput(
              lines: [OdometerOcrLineInput(text: '678 km')],
            ),
          ],
        ),
      );

      expect(_values(result), [12, 345, 678]);
      expect(_values(result), isNot(contains(12345)));
    });

    test('joins split numeric elements only when geometry proves one run', () {
      final close = parser.parse(_elementDocument(secondLeft: 30));
      final far = parser.parse(_elementDocument(secondLeft: 100));

      expect(_values(close), [541]);
      expect(_values(far), [5, 41]);
      expect(close.single.bounds?.right, 60);
    });

    test(
      'retains decimal, unit, label, variant, and substitution evidence',
      () {
        final result = parser.parse(
          _document('ODO 12S45.6 km', variant: 'enhanced'),
        );
        final candidate = result.single;

        expect(candidate.readingKm, 12545);
        expect(candidate.sourceText, '12S45.6');
        expect(candidate.normalizedDigits, '12545');
        expect(candidate.separators, ['.']);
        expect(candidate.decimalEvidence, OdometerDecimalEvidence.tenths);
        expect(candidate.hasDistanceUnit, isTrue);
        expect(candidate.hasOdometerLabel, isTrue);
        expect(candidate.variant, 'enhanced');
        expect(candidate.substitutions, hasLength(1));
        expect(candidate.substitutions.single.source, 'S');
        expect(candidate.substitutions.single.digit, '5');
      },
    );

    test('does not apply glyph substitutions to ordinary labels', () {
      final result = parser.parse(_document('SPEED ODO 808'));
      expect(_values(result), [808]);
      expect(result.single.sourceText, '808');
      expect(result.single.substitutions, isEmpty);
    });

    test('plain spaces are not silently treated as grouping', () {
      expect(_values(parser.parse(_document('ODO 5 41 km'))), [5, 41]);
      expect(_values(parser.parse(_document('ODO 1 234 km'))), [1234]);
    });
  });

  test('fuzz input is deterministic, bounded, and never throws', () {
    final random = Random(88421);
    const alphabet = '0123456789ODO km/h,.:-_|!SBrange\n';
    for (var caseIndex = 0; caseIndex < 1000; caseIndex++) {
      final length = random.nextInt(80);
      final text = String.fromCharCodes(
        List.generate(
          length,
          (_) => alphabet.codeUnitAt(random.nextInt(alphabet.length)),
        ),
      );
      final document = _document(text);
      final first = parser.parse(document);
      final second = parser.parse(document);
      expect(_signatures(first), _signatures(second));
      for (final candidate in first) {
        expect(candidate.readingKm, inInclusiveRange(1, 9_999_999));
      }
    }
  });
}

OdometerOcrDocumentInput _document(
  String text, {
  String variant = 'normalized',
}) => OdometerOcrDocumentInput(
  variant: variant,
  blocks: [
    OdometerOcrBlockInput(lines: [OdometerOcrLineInput(text: text)]),
  ],
);

OdometerOcrDocumentInput _elementDocument({required double secondLeft}) =>
    OdometerOcrDocumentInput(
      variant: 'normalized',
      blocks: [
        OdometerOcrBlockInput(
          lines: [
            OdometerOcrLineInput(
              text: '5 41 km',
              elements: [
                OdometerOcrElementInput(
                  text: '5',
                  bounds: OdometerOcrRect(
                    left: 10,
                    top: 10,
                    right: 22,
                    bottom: 40,
                  ),
                ),
                OdometerOcrElementInput(
                  text: '41',
                  bounds: OdometerOcrRect(
                    left: secondLeft,
                    top: 10,
                    right: secondLeft + 30,
                    bottom: 40,
                  ),
                ),
              ],
            ),
          ],
        ),
      ],
    );

List<int> _values(List<ParsedOdometerCandidate> candidates) =>
    candidates.map((candidate) => candidate.readingKm).toList();

List<String> _signatures(List<ParsedOdometerCandidate> candidates) => candidates
    .map(
      (candidate) =>
          '${candidate.blockIndex}:${candidate.lineIndex}:${candidate.readingKm}:${candidate.sourceText}',
    )
    .toList();
