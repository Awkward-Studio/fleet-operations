import 'dart:convert';

enum OdometerSecondaryStatus {
  disabled,
  unsupported,
  unavailable,
  downloadable,
  downloading,
  available,
  busy,
  quotaExceeded,
  timedOut,
  cancelled,
  malformedOutput,
  failed,
}

class OdometerSecondaryReading {
  const OdometerSecondaryReading({
    required this.status,
    this.readingKm,
    this.isOdometer = false,
    this.modelVersion,
    this.elapsed,
  }) : assert(
         status == OdometerSecondaryStatus.available || readingKm == null,
         'Unavailable providers cannot return a reading.',
       ),
       assert(readingKm == null || (readingKm >= 1 && readingKm <= 9_999_999));

  final OdometerSecondaryStatus status;
  final int? readingKm;
  final bool isOdometer;
  final String? modelVersion;
  final Duration? elapsed;

  /// A secondary result is evidence only. It never independently authorizes
  /// prefilling or submission.
  bool get isUsableEvidence =>
      status == OdometerSecondaryStatus.available &&
      isOdometer &&
      readingKm != null;
}

abstract interface class OdometerSecondaryRecognizer {
  Future<OdometerSecondaryStatus> checkStatus();

  Future<OdometerSecondaryReading> recognize({
    required String preparedImagePath,
    required String deterministicSummary,
    required int referenceKm,
    required String mode,
  });
}

class DisabledOdometerSecondaryRecognizer
    implements OdometerSecondaryRecognizer {
  const DisabledOdometerSecondaryRecognizer();

  @override
  Future<OdometerSecondaryStatus> checkStatus() async =>
      OdometerSecondaryStatus.disabled;

  @override
  Future<OdometerSecondaryReading> recognize({
    required String preparedImagePath,
    required String deterministicSummary,
    required int referenceKm,
    required String mode,
  }) async =>
      const OdometerSecondaryReading(status: OdometerSecondaryStatus.disabled);
}

/// Strict parser for a future native Prompt API bridge. Prose, extra keys,
/// floats, numeric strings, invalid ranges, and contradictory output fail shut.
OdometerSecondaryReading parseSecondaryStructuredOutput(
  String source, {
  String? modelVersion,
  Duration? elapsed,
}) {
  try {
    final decoded = jsonDecode(source);
    if (decoded is! Map<String, Object?> ||
        !const {
          'reading_km',
          'is_odometer',
          'reason_code',
        }.containsAll(decoded.keys) ||
        decoded.keys.length != 3 ||
        decoded['is_odometer'] is! bool ||
        decoded['reason_code'] is! String) {
      return const OdometerSecondaryReading(
        status: OdometerSecondaryStatus.malformedOutput,
      );
    }
    final isOdometer = decoded['is_odometer']! as bool;
    final reading = decoded['reading_km'];
    if (reading != null && reading is! int ||
        reading is int && (reading < 1 || reading > 9_999_999) ||
        isOdometer != (reading != null)) {
      return const OdometerSecondaryReading(
        status: OdometerSecondaryStatus.malformedOutput,
      );
    }
    return OdometerSecondaryReading(
      status: OdometerSecondaryStatus.available,
      readingKm: reading as int?,
      isOdometer: isOdometer,
      modelVersion: modelVersion,
      elapsed: elapsed,
    );
  } on FormatException {
    return const OdometerSecondaryReading(
      status: OdometerSecondaryStatus.malformedOutput,
    );
  }
}
