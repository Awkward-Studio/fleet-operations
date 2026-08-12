import 'dart:io';

import 'package:driver_app/core/odometer_ocr_contract.dart';
import 'package:driver_app/core/odometer_ocr_evaluation.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  late OdometerCorpus corpus;

  setUpAll(() async {
    corpus = decodeOdometerCorpus(
      await File('test/fixtures/odometer_ocr/manifest.json').readAsString(),
    );
  });

  test('manifest has unique privacy-safe coverage in every category', () {
    expect(corpus.cases, hasLength(60));
    expect(corpus.cases.map((fixture) => fixture.id).toSet(), hasLength(60));
    for (final category in const {
      'mechanical',
      'lcd',
      'seven_segment',
      'multi_number',
      'degraded',
      'negative',
    }) {
      expect(
        corpus.cases.where((fixture) => fixture.displayType == category),
        hasLength(10),
      );
    }
    expect(
      corpus.cases.every(
        (fixture) =>
            fixture.privacy.classification == 'synthetic' &&
            fixture.privacy.consent == 'not_required' &&
            fixture.privacy.exifStripped,
      ),
      isTrue,
    );
  });

  test('legacy baseline is reproducible and exposes pre-fix failures', () {
    final first = evaluateOdometerCorpus(corpus, legacyTextBaseline).toJson();
    final second = evaluateOdometerCorpus(corpus, legacyTextBaseline).toJson();

    expect(second, first);
    expect(first['total'], 60);
    expect(first['incorrect_autofills'], greaterThan(0));
    expect(first['abstentions'], greaterThan(0));
    expect(first['latency'], {'samples': 0});
  });

  test(
    'parser-only corpus evaluation is reproducible and retains evidence',
    () {
      final first = evaluateParserCorpus(corpus).toJson();
      final second = evaluateParserCorpus(corpus).toJson();

      expect(second, first);
      expect(first['total'], 60);
      expect(first['expected_candidate_cases'], 40);
      final diagnostics = first['diagnostics']! as Map<String, Object?>;
      for (final entries in diagnostics.values) {
        for (final entry in entries! as List<Object?>) {
          expect((entry! as Map<String, Object?>)['source_text'], isNotEmpty);
        }
      }
    },
  );

  test('scoring policy is reported separately on frozen held-out cases', () {
    final heldOut = corpusPartition(corpus, heldOut: true);
    final first = evaluateOdometerCorpus(
      heldOut,
      parserScoringBaseline,
    ).toJson();
    final second = evaluateOdometerCorpus(
      heldOut,
      parserScoringBaseline,
    ).toJson();

    expect(heldOut.cases, hasLength(12));
    expect(second, first);
    expect(first['incorrect_autofills'], 0);
  });

  test('evaluator reports latency when a provider supplies it', () {
    final report = evaluateOdometerCorpus(
      corpus,
      (fixture) => OdometerEvaluationPrediction(
        decision: fixture.expectedDecision,
        readingKm: fixture.expectedDecision == OdometerOcrDecision.accepted
            ? fixture.expectedKm
            : null,
        latency: const Duration(milliseconds: 12),
      ),
    );

    expect(report.exactMatchRate, 1);
    expect(report.incorrectAutofillRate, 0);
    expect(report.toJson()['latency'], {
      'samples': 60,
      'median_ms': 12.0,
      'p95_ms': 12.0,
    });
  });

  test('real fixtures require consent and stripped EXIF', () {
    expect(
      () => CorpusPrivacy.fromJson({
        'classification': 'sanitized_real',
        'consent': 'not_required',
        'exif_stripped': true,
      }),
      throwsFormatException,
    );
  });
}
