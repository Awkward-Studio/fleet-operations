import 'package:flutter_test/flutter_test.dart';

import 'package:driver_app/core/odometer_ocr_contract.dart';
import 'package:driver_app/core/odometer_ocr_parser.dart';
import 'package:driver_app/core/odometer_ocr_scorer.dart';

void main() {
  const scorer = OdometerCandidateScorer();

  test('returns no-reading when no viable candidate exists', () {
    final outcome = scorer.decide(_input(const []));
    expect(outcome.decision, OdometerOcrDecision.noReading);
    expect(outcome.reasonCode, OdometerOcrReasonCode.noCandidate);
    expect(outcome.mayPrefill, isFalse);
  });

  test('accepts one strongly supported plausible candidate', () {
    final outcome = scorer.decide(
      _input([_observation(541, label: true, unit: true)]),
    );
    expect(outcome.decision, OdometerOcrDecision.accepted);
    expect(outcome.selectedReadingKm, 541);
    expect(outcome.candidates.single.score, greaterThanOrEqualTo(50));
  });

  test('aggregates extractor and variant evidence before deduplication', () {
    final outcome = scorer.decide(
      _input([
        _observation(541, variant: 'normalized', extractor: 'line-token'),
        _observation(541, variant: 'enhanced', extractor: 'element-run'),
      ]),
    );
    final evidence = outcome.candidates.single.evidence;
    expect(evidence.variantCount, 2);
    expect(evidence.extractors, {'line-token', 'element-run'});
    expect(evidence.observationCount, 2);
  });

  test(
    'geometry, labels, units, continuity, and substitutions affect score',
    () {
      final weak = scorer.decide(
        _input([_observation(541, substitutions: 2, source: 'S4I')]),
      );
      final strong = scorer.decide(
        _input(
          [
            _observation(
              542,
              label: true,
              unit: true,
              bounds: const OdometerOcrRect(
                left: 250,
                top: 80,
                right: 750,
                bottom: 220,
              ),
            ),
          ],
          width: 1000,
          height: 300,
        ),
      );
      expect(
        strong.candidates.single.score,
        greaterThan(weak.candidates.single.score),
      );
      expect(
        strong.candidates.single.evidence.relativeDigitHeight,
        closeTo(0.467, 0.001),
      );
      expect(
        strong.candidates.single.evidence.cropCentrality,
        greaterThan(0.9),
      );
    },
  );

  test('below-reference readings never auto-accept', () {
    final outcome = scorer.decide(
      _input([_observation(499, label: true, unit: true)]),
    );
    expect(outcome.decision, OdometerOcrDecision.needsReview);
    expect(outcome.reasonCode, OdometerOcrReasonCode.belowReference);
    expect(outcome.selectedReadingKm, isNull);
  });

  test('end mode requires a strict increase while start permits equality', () {
    final end = scorer.decide(
      _input([
        _observation(500, label: true, unit: true),
      ], mode: OdometerScanMode.end),
    );
    final start = scorer.decide(
      _input([_observation(500, label: true, unit: true)]),
    );
    expect(end.reasonCode, OdometerOcrReasonCode.belowReference);
    expect(start.decision, OdometerOcrDecision.accepted);
  });

  test('mode-specific and request-specific excessive deltas abstain', () {
    final defaultEnd = scorer.decide(
      _input([
        _observation(2501, label: true, unit: true),
      ], mode: OdometerScanMode.end),
    );
    final override = scorer.decide(
      _input([_observation(601, label: true, unit: true)], maximumDelta: 100),
    );
    expect(defaultEnd.reasonCode, OdometerOcrReasonCode.excessiveDelta);
    expect(override.reasonCode, OdometerOcrReasonCode.excessiveDelta);
  });

  test('conflicting top candidates inside the margin require review', () {
    final outcome = scorer.decide(
      _input([
        _observation(541, label: true, unit: true),
        _observation(542, label: true, unit: true),
      ]),
    );
    expect(outcome.decision, OdometerOcrDecision.needsReview);
    expect(outcome.reasonCode, OdometerOcrReasonCode.ambiguous);
  });

  test('threshold edge is accepted and just below it is review', () {
    final edgeScorer = OdometerCandidateScorer(
      policy: const OdometerScoringPolicy(acceptanceThreshold: 50),
    );
    final edge = edgeScorer.decide(_input([_observation(541, unit: true)]));
    final below = OdometerCandidateScorer(
      policy: OdometerScoringPolicy(
        acceptanceThreshold: edge.candidates.single.score + 0.01,
      ),
    ).decide(_input([_observation(541, unit: true)]));
    expect(edge.decision, OdometerOcrDecision.accepted);
    expect(below.decision, OdometerOcrDecision.needsReview);
  });

  test('quality issues override otherwise acceptable evidence', () {
    final outcome = scorer.decide(
      _input(
        [_observation(541, label: true, unit: true)],
        qualityIssues: const [OdometerQualityIssue.blurred],
      ),
    );
    expect(outcome.decision, OdometerOcrDecision.needsReview);
    expect(outcome.reasonCode, OdometerOcrReasonCode.imageQuality);
  });

  test('ties are ordered deterministically by reading', () {
    final observations = [
      _observation(542, label: true, unit: true),
      _observation(541, label: true, unit: true),
    ];
    final first = scorer.decide(_input(observations));
    final second = scorer.decide(_input(observations.reversed.toList()));
    expect(first.candidates.map((item) => item.readingKm), [541, 542]);
    expect(second.candidates.map((item) => item.readingKm), [541, 542]);
  });
}

OdometerScoringInput _input(
  List<ParsedOdometerCandidate> observations, {
  OdometerScanMode mode = OdometerScanMode.start,
  int? maximumDelta,
  double? width,
  double? height,
  List<OdometerQualityIssue> qualityIssues = const [],
}) => OdometerScoringInput(
  request: OdometerOcrRequest(
    imagePath: 'fixture.jpg',
    mode: mode,
    referenceKm: 500,
    maximumDeltaKm: maximumDelta,
  ),
  observations: observations,
  imageWidth: width,
  imageHeight: height,
  qualityIssues: qualityIssues,
);

ParsedOdometerCandidate _observation(
  int value, {
  String variant = 'normalized',
  String extractor = 'line-token',
  bool label = false,
  bool unit = false,
  int substitutions = 0,
  String source = '541',
  OdometerOcrRect? bounds,
}) => ParsedOdometerCandidate(
  readingKm: value,
  sourceText: source,
  normalizedDigits: value.toString(),
  separators: const [],
  hasDistanceUnit: unit,
  hasOdometerLabel: label,
  decimalEvidence: OdometerDecimalEvidence.none,
  substitutions: List.generate(
    substitutions,
    (index) =>
        OdometerGlyphSubstitution(offset: index, source: 'S', digit: '5'),
  ),
  variant: variant,
  extractor: extractor,
  blockIndex: 0,
  lineIndex: 0,
  bounds: bounds,
);
