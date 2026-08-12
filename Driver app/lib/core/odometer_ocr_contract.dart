/// Stable domain contract for odometer recognition.
///
/// Platform recognizers, deterministic parsers, optional secondary providers,
/// and the driver UI all communicate through these types. A candidate score is
/// deliberately named [score], not confidence: it is an explainable ranking
/// signal and must not be displayed as a calibrated probability.
enum OdometerScanMode { start, end }

enum OdometerOcrDecision { accepted, needsReview, noReading }

enum OdometerOcrReasonCode {
  accepted,
  imageQuality,
  noCandidate,
  ambiguous,
  belowReference,
  excessiveDelta,
  providerUnavailable,
  providerError,
  cancelled,
}

enum OdometerQualityIssue {
  tooSmall,
  blurred,
  underexposed,
  overexposed,
  lowContrast,
  clipped,
  glare,
  unsupportedOrientation,
}

class OdometerOcrRequest {
  const OdometerOcrRequest({
    required this.imagePath,
    required this.mode,
    required this.referenceKm,
    this.maximumDeltaKm,
  }) : assert(referenceKm >= 0),
       assert(maximumDeltaKm == null || maximumDeltaKm > 0);

  final String imagePath;
  final OdometerScanMode mode;
  final int referenceKm;
  final int? maximumDeltaKm;
}

class OdometerCandidateEvidence {
  const OdometerCandidateEvidence({
    required this.extractors,
    required this.variantCount,
    required this.relativeDigitHeight,
    required this.cropCentrality,
    required this.hasDistanceUnit,
    required this.substitutionCount,
    this.hasOdometerLabel = false,
    this.horizontalContinuity = 0,
    this.observationCount = 1,
  }) : assert(variantCount > 0),
       assert(relativeDigitHeight >= 0 && relativeDigitHeight <= 1),
       assert(cropCentrality >= 0 && cropCentrality <= 1),
       assert(substitutionCount >= 0),
       assert(horizontalContinuity >= 0 && horizontalContinuity <= 1),
       assert(observationCount > 0);

  final Set<String> extractors;
  final int variantCount;
  final double relativeDigitHeight;
  final double cropCentrality;
  final bool hasDistanceUnit;
  final int substitutionCount;
  final bool hasOdometerLabel;
  final double horizontalContinuity;
  final int observationCount;
}

class OdometerOcrCandidate {
  const OdometerOcrCandidate({
    required this.readingKm,
    required this.score,
    required this.evidence,
  }) : assert(readingKm >= 1 && readingKm <= 9_999_999);

  final int readingKm;

  /// An uncalibrated, deterministic ranking score. This is not a probability.
  final double score;
  final OdometerCandidateEvidence evidence;
}

class OdometerOcrOutcome {
  const OdometerOcrOutcome({
    required this.decision,
    required this.reasonCode,
    required this.candidates,
    required this.qualityIssues,
    required this.elapsed,
    this.selectedReadingKm,
  }) : assert(
         decision == OdometerOcrDecision.accepted
             ? selectedReadingKm != null
             : selectedReadingKm == null,
         'Only an accepted outcome may expose a selected reading.',
       );

  final OdometerOcrDecision decision;
  final OdometerOcrReasonCode reasonCode;
  final int? selectedReadingKm;
  final List<OdometerOcrCandidate> candidates;
  final List<OdometerQualityIssue> qualityIssues;
  final Duration elapsed;

  bool get mayPrefill => decision == OdometerOcrDecision.accepted;
}
