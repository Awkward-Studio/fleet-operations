import 'dart:async';

import 'odometer_image_preprocessor.dart';
import 'odometer_ocr_contract.dart';
import 'odometer_ocr_parser.dart';
import 'odometer_ocr_scorer.dart';

class OdometerCancellationToken {
  bool _cancelled = false;

  bool get isCancelled => _cancelled;
  void cancel() => _cancelled = true;
}

class OdometerPreparedVariant {
  const OdometerPreparedVariant({required this.name, required this.path});
  final String name;
  final String path;
}

class OdometerPreparedScan {
  const OdometerPreparedScan({
    required this.variants,
    required this.width,
    required this.height,
    required this.qualityIssues,
    required this.cleanup,
  });

  final List<OdometerPreparedVariant> variants;
  final int width;
  final int height;
  final List<OdometerQualityIssue> qualityIssues;
  final Future<void> Function() cleanup;
}

abstract interface class OdometerImagePreparationGateway {
  Future<OdometerPreparedScan> prepare(
    String imagePath, {
    required bool Function() isCancelled,
  });
}

class DefaultOdometerImagePreparationGateway
    implements OdometerImagePreparationGateway {
  factory DefaultOdometerImagePreparationGateway({
    OdometerImagePreprocessor preprocessor = const OdometerImagePreprocessor(),
  }) => DefaultOdometerImagePreparationGateway._(preprocessor);

  DefaultOdometerImagePreparationGateway._(this._preprocessor);

  final OdometerImagePreprocessor _preprocessor;

  @override
  Future<OdometerPreparedScan> prepare(
    String imagePath, {
    required bool Function() isCancelled,
  }) async {
    final prepared = await _preprocessor.prepare(
      imagePath,
      isCancelled: isCancelled,
    );
    return OdometerPreparedScan(
      variants: List.unmodifiable([
        for (final variant in prepared.variants)
          OdometerPreparedVariant(name: variant.kind.name, path: variant.path),
      ]),
      width: prepared.width,
      height: prepared.height,
      qualityIssues: prepared.qualityIssues,
      cleanup: prepared.dispose,
    );
  }
}

abstract interface class OdometerTextRecognitionGateway {
  Future<OdometerOcrDocumentInput> recognize(
    String imagePath, {
    required String variant,
  });

  Future<void> close();
}

abstract interface class OdometerDiagnosticSink {
  void record(Map<String, Object?> event);
}

class NoopOdometerDiagnosticSink implements OdometerDiagnosticSink {
  const NoopOdometerDiagnosticSink();
  @override
  void record(Map<String, Object?> event) {}
}

class OdometerOcrCoordinator {
  factory OdometerOcrCoordinator({
    required OdometerImagePreparationGateway preparer,
    required OdometerTextRecognitionGateway recognizer,
    OdometerOcrParser parser = const OdometerOcrParser(),
    OdometerCandidateScorer scorer = const OdometerCandidateScorer(),
    OdometerDiagnosticSink diagnostics = const NoopOdometerDiagnosticSink(),
    Duration recognitionTimeout = const Duration(seconds: 8),
  }) => OdometerOcrCoordinator._(
    preparer,
    recognizer,
    parser,
    scorer,
    diagnostics,
    recognitionTimeout,
  );

  OdometerOcrCoordinator._(
    this._preparer,
    this._recognizer,
    this._parser,
    this._scorer,
    this._diagnostics,
    this.recognitionTimeout,
  );

  final OdometerImagePreparationGateway _preparer;
  final OdometerTextRecognitionGateway _recognizer;
  final OdometerOcrParser _parser;
  final OdometerCandidateScorer _scorer;
  final OdometerDiagnosticSink _diagnostics;
  final Duration recognitionTimeout;

  Future<void> _tail = Future.value();
  bool _closed = false;
  bool _recognizerClosed = false;
  int _requestSequence = 0;

  Future<OdometerOcrOutcome> scan(
    OdometerOcrRequest request, {
    OdometerCancellationToken? cancellationToken,
  }) {
    final token = cancellationToken ?? OdometerCancellationToken();
    final requestId = ++_requestSequence;
    final completer = Completer<OdometerOcrOutcome>();
    _tail = _tail.then((_) async {
      if (_closed) {
        completer.completeError(StateError('OCR coordinator is closed.'));
        return;
      }
      try {
        completer.complete(await _run(request, token, requestId));
      } catch (error, stackTrace) {
        completer.completeError(error, stackTrace);
      }
    });
    return completer.future;
  }

  Future<OdometerOcrOutcome> _run(
    OdometerOcrRequest request,
    OdometerCancellationToken token,
    int requestId,
  ) async {
    final stopwatch = Stopwatch()..start();
    OdometerPreparedScan? prepared;
    var variantCount = 0;
    var diagnosticReason = OdometerOcrReasonCode.providerError;
    OdometerOcrOutcome publish(OdometerOcrOutcome outcome) {
      diagnosticReason = outcome.reasonCode;
      return outcome;
    }

    try {
      if (token.isCancelled) return publish(_cancelled(stopwatch.elapsed));
      prepared = await _preparer.prepare(
        request.imagePath,
        isCancelled: () => token.isCancelled || _closed,
      );
      if (token.isCancelled || _closed) {
        return publish(_cancelled(stopwatch.elapsed));
      }

      if (prepared.qualityIssues.isNotEmpty) {
        return publish(
          _scorer.decide(
            OdometerScoringInput(
              request: request,
              observations: const [],
              imageWidth: prepared.width.toDouble(),
              imageHeight: prepared.height.toDouble(),
              qualityIssues: prepared.qualityIssues,
            ),
          ),
        );
      }

      final observations = <ParsedOdometerCandidate>[];
      for (final variant in prepared.variants) {
        if (token.isCancelled || _closed) {
          return publish(_cancelled(stopwatch.elapsed));
        }
        final document = await _recognizeWithTimeout(variant);
        variantCount++;
        observations.addAll(_parser.parse(document));
      }
      if (token.isCancelled || _closed) {
        return publish(_cancelled(stopwatch.elapsed));
      }
      return publish(
        _scorer.decide(
          OdometerScoringInput(
            request: request,
            observations: observations,
            imageWidth: prepared.width.toDouble(),
            imageHeight: prepared.height.toDouble(),
          ),
        ),
      );
    } on TimeoutException {
      return publish(
        _failure(OdometerOcrReasonCode.providerError, stopwatch.elapsed),
      );
    } catch (_) {
      if (token.isCancelled || _closed) {
        return publish(_cancelled(stopwatch.elapsed));
      }
      return publish(
        _failure(OdometerOcrReasonCode.providerError, stopwatch.elapsed),
      );
    } finally {
      var cleanupFailed = false;
      try {
        await prepared?.cleanup();
      } catch (_) {
        cleanupFailed = true;
      }
      _diagnostics.record(
        Map.unmodifiable({
          'event': 'odometer_ocr_completed',
          'request_id': requestId,
          'mode': request.mode.name,
          'elapsed_ms': stopwatch.elapsedMilliseconds,
          'variants_processed': variantCount,
          'cancelled': token.isCancelled || _closed,
          'reason_code': diagnosticReason.name,
          'cleanup_failed': cleanupFailed,
        }),
      );
    }
  }

  Future<OdometerOcrDocumentInput> _recognizeWithTimeout(
    OdometerPreparedVariant variant,
  ) async {
    final pending = _recognizer.recognize(variant.path, variant: variant.name);
    try {
      return await pending.timeout(recognitionTimeout);
    } on TimeoutException {
      // ML Kit does not expose per-request cancellation. Wait for the native
      // call to settle before releasing the serialization guard.
      try {
        await pending;
      } catch (_) {}
      rethrow;
    }
  }

  OdometerOcrOutcome _cancelled(Duration elapsed) => OdometerOcrOutcome(
    decision: OdometerOcrDecision.noReading,
    reasonCode: OdometerOcrReasonCode.cancelled,
    candidates: const [],
    qualityIssues: const [],
    elapsed: elapsed,
  );

  OdometerOcrOutcome _failure(OdometerOcrReasonCode reason, Duration elapsed) =>
      OdometerOcrOutcome(
        decision: OdometerOcrDecision.noReading,
        reasonCode: reason,
        candidates: const [],
        qualityIssues: const [],
        elapsed: elapsed,
      );

  Future<void> close() async {
    if (_closed) return;
    _closed = true;
    await _tail;
    if (!_recognizerClosed) {
      _recognizerClosed = true;
      await _recognizer.close();
    }
  }
}
