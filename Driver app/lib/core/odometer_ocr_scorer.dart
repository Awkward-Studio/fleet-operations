import 'dart:math' as math;

import 'odometer_ocr_contract.dart';
import 'odometer_ocr_parser.dart';

class OdometerScoringPolicy {
  const OdometerScoringPolicy({
    this.acceptanceThreshold = 46,
    this.ambiguityMargin = 12,
    this.startMaximumDeltaKm = 500,
    this.endMaximumDeltaKm = 1000,
  });

  final double acceptanceThreshold;
  final double ambiguityMargin;
  final int startMaximumDeltaKm;
  final int endMaximumDeltaKm;
}

class OdometerScoringInput {
  const OdometerScoringInput({
    required this.request,
    required this.observations,
    this.imageWidth,
    this.imageHeight,
    this.qualityIssues = const [],
  });

  final OdometerOcrRequest request;
  final List<ParsedOdometerCandidate> observations;
  final double? imageWidth;
  final double? imageHeight;
  final List<OdometerQualityIssue> qualityIssues;
}

class OdometerCandidateScorer {
  const OdometerCandidateScorer({this.policy = const OdometerScoringPolicy()});

  final OdometerScoringPolicy policy;

  OdometerOcrOutcome decide(OdometerScoringInput input) {
    final stopwatch = Stopwatch()..start();
    final grouped = <int, List<ParsedOdometerCandidate>>{};
    for (final observation in input.observations) {
      grouped.putIfAbsent(observation.readingKm, () => []).add(observation);
    }
    final candidates =
        [
          for (final entry in grouped.entries)
            _score(entry.key, entry.value, input.imageWidth, input.imageHeight),
        ]..sort((a, b) {
          final scoreOrder = b.score.compareTo(a.score);
          return scoreOrder != 0
              ? scoreOrder
              : a.readingKm.compareTo(b.readingKm);
        });

    if (candidates.isEmpty) {
      return OdometerOcrOutcome(
        decision: OdometerOcrDecision.noReading,
        reasonCode: input.qualityIssues.isEmpty
            ? OdometerOcrReasonCode.noCandidate
            : OdometerOcrReasonCode.imageQuality,
        candidates: const [],
        qualityIssues: List.unmodifiable(input.qualityIssues),
        elapsed: stopwatch.elapsed,
      );
    }

    OdometerOcrOutcome review(OdometerOcrReasonCode reason) =>
        OdometerOcrOutcome(
          decision: OdometerOcrDecision.needsReview,
          reasonCode: reason,
          candidates: List.unmodifiable(candidates),
          qualityIssues: List.unmodifiable(input.qualityIssues),
          elapsed: stopwatch.elapsed,
        );

    if (input.qualityIssues.isNotEmpty) {
      return review(OdometerOcrReasonCode.imageQuality);
    }
    final top = candidates.first;
    final belowReference = input.request.mode == OdometerScanMode.end
        ? top.readingKm <= input.request.referenceKm
        : top.readingKm < input.request.referenceKm;
    if (belowReference) return review(OdometerOcrReasonCode.belowReference);

    final allowedDelta =
        input.request.maximumDeltaKm ??
        (input.request.mode == OdometerScanMode.start
            ? policy.startMaximumDeltaKm
            : policy.endMaximumDeltaKm);
    if (top.readingKm - input.request.referenceKm > allowedDelta) {
      return review(OdometerOcrReasonCode.excessiveDelta);
    }
    if (top.score < policy.acceptanceThreshold) {
      return review(OdometerOcrReasonCode.ambiguous);
    }
    if (candidates.length > 1 &&
        top.score - candidates[1].score < policy.ambiguityMargin) {
      return review(OdometerOcrReasonCode.ambiguous);
    }

    return OdometerOcrOutcome(
      decision: OdometerOcrDecision.accepted,
      reasonCode: OdometerOcrReasonCode.accepted,
      selectedReadingKm: top.readingKm,
      candidates: List.unmodifiable(candidates),
      qualityIssues: const [],
      elapsed: stopwatch.elapsed,
    );
  }

  OdometerOcrCandidate _score(
    int reading,
    List<ParsedOdometerCandidate> observations,
    double? imageWidth,
    double? imageHeight,
  ) {
    final variants = observations.map((item) => item.variant).toSet();
    final extractors = observations.map((item) => item.extractor).toSet();
    final substitutions = observations
        .map((item) => item.substitutions.length)
        .reduce(math.min);
    final hasLabel = observations.any((item) => item.hasOdometerLabel);
    final hasUnit = observations.any((item) => item.hasDistanceUnit);
    final continuity = observations.map(_horizontalContinuity).reduce(math.max);
    final relativeHeight = observations
        .map((item) => _relativeHeight(item.bounds, imageHeight))
        .reduce(math.max);
    final centrality = observations
        .map((item) => _centrality(item.bounds, imageWidth, imageHeight))
        .reduce(math.max);
    final hasDecimal = observations.any(
      (item) => item.decimalEvidence != OdometerDecimalEvidence.none,
    );
    final substitutionPenalty = substitutions * (hasLabel || hasUnit ? 1 : 3);

    final score =
        12 +
        12 +
        ((variants.length - 1) * 14) +
        6 +
        ((extractors.length - 1) * 6) +
        (hasLabel ? 18 : 0) +
        (hasUnit ? 12 : 0) +
        (relativeHeight * 20) +
        (centrality * 10) +
        (continuity * 8) -
        substitutionPenalty -
        (hasDecimal ? 6 : 0);

    return OdometerOcrCandidate(
      readingKm: reading,
      score: score,
      evidence: OdometerCandidateEvidence(
        extractors: Set.unmodifiable(extractors),
        variantCount: variants.length,
        relativeDigitHeight: relativeHeight,
        cropCentrality: centrality,
        hasDistanceUnit: hasUnit,
        substitutionCount: substitutions,
        hasOdometerLabel: hasLabel,
        horizontalContinuity: continuity,
        observationCount: observations.length,
      ),
    );
  }

  double _horizontalContinuity(ParsedOdometerCandidate item) {
    if (item.normalizedDigits.isEmpty) return 0;
    final separatorPenalty = item.separators.length * 0.08;
    return (1 - separatorPenalty).clamp(0, 1);
  }

  double _relativeHeight(OdometerOcrRect? bounds, double? imageHeight) {
    if (bounds == null || imageHeight == null || imageHeight <= 0) return 0;
    return (bounds.height / imageHeight).clamp(0, 1);
  }

  double _centrality(
    OdometerOcrRect? bounds,
    double? imageWidth,
    double? imageHeight,
  ) {
    if (bounds == null ||
        imageWidth == null ||
        imageHeight == null ||
        imageWidth <= 0 ||
        imageHeight <= 0) {
      return 0;
    }
    final centerX = (bounds.left + bounds.right) / 2;
    final centerY = (bounds.top + bounds.bottom) / 2;
    final normalizedDistance = math.sqrt(
      math.pow((centerX - imageWidth / 2) / (imageWidth / 2), 2) +
          math.pow((centerY - imageHeight / 2) / (imageHeight / 2), 2),
    );
    return (1 - (normalizedDistance / math.sqrt(2))).clamp(0, 1);
  }
}
