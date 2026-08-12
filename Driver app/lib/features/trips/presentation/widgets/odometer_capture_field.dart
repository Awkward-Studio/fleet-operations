import 'dart:io';

import 'package:flutter/material.dart';
import 'package:image_cropper/image_cropper.dart';
import 'package:image_picker/image_picker.dart';

import '../../../../core/odometer_image_preprocessor.dart';
import '../../../../core/odometer_ocr_contract.dart';
import '../../../../core/odometer_ocr_coordinator.dart';
import '../../../../core/odometer_ocr_service.dart';

enum OdometerCaptureState {
  idle,
  capturing,
  reviewingCrop,
  scanning,
  accepted,
  needsReview,
  noReading,
  error,
}

enum OdometerReadingSource { manual, ocrConfirmed, ocrCorrected }

extension OdometerReadingSourceApi on OdometerReadingSource {
  String get apiValue => switch (this) {
    OdometerReadingSource.manual => 'MANUAL',
    OdometerReadingSource.ocrConfirmed => 'OCR_CONFIRMED',
    OdometerReadingSource.ocrCorrected => 'OCR_CORRECTED',
  };
}

class OdometerCaptureSnapshot {
  const OdometerCaptureSnapshot({
    this.state = OdometerCaptureState.idle,
    this.photoPath,
    this.confirmed = false,
    this.source = OdometerReadingSource.manual,
    this.overrideReason = '',
    this.outcome,
  });

  final OdometerCaptureState state;
  final String? photoPath;
  final bool confirmed;
  final OdometerReadingSource source;
  final String overrideReason;
  final OdometerOcrOutcome? outcome;

  bool get scanning => state == OdometerCaptureState.scanning;
  bool get requiresOverrideReason =>
      outcome?.reasonCode == OdometerOcrReasonCode.belowReference ||
      outcome?.reasonCode == OdometerOcrReasonCode.excessiveDelta;
  bool get canSubmit =>
      photoPath != null &&
      confirmed &&
      !scanning &&
      (!requiresOverrideReason || overrideReason.trim().isNotEmpty);

  String? get clientDecisionApiValue => switch (source) {
    OdometerReadingSource.manual => null,
    OdometerReadingSource.ocrConfirmed => 'ACCEPTED',
    OdometerReadingSource.ocrCorrected => 'NEEDS_REVIEW',
  };
}

typedef OdometerPhotoCapture = Future<String?> Function(BuildContext context);
typedef OdometerScan =
    Future<OdometerOcrOutcome> Function(
      OdometerOcrRequest request,
      OdometerCancellationToken token,
    );

class OdometerCaptureField extends StatefulWidget {
  const OdometerCaptureField({
    super.key,
    required this.controller,
    required this.mode,
    required this.referenceKm,
    required this.onChanged,
    this.capturePhoto,
    this.scan,
    this.photoBuilder,
  });

  final TextEditingController controller;
  final OdometerScanMode mode;
  final int referenceKm;
  final ValueChanged<OdometerCaptureSnapshot> onChanged;
  final OdometerPhotoCapture? capturePhoto;
  final OdometerScan? scan;
  final Widget Function(BuildContext context, String path)? photoBuilder;

  @override
  State<OdometerCaptureField> createState() => _OdometerCaptureFieldState();
}

class _OdometerCaptureFieldState extends State<OdometerCaptureField> {
  OdometerCaptureSnapshot _snapshot = const OdometerCaptureSnapshot();
  OdometerCancellationToken? _token;
  int _editRevision = 0;
  bool _applyingOcr = false;

  @override
  void initState() {
    super.initState();
    widget.controller.addListener(_manualEdit);
  }

  @override
  void dispose() {
    _token?.cancel();
    widget.controller.removeListener(_manualEdit);
    super.dispose();
  }

  void _manualEdit() {
    if (_applyingOcr) return;
    _editRevision++;
    if (!mounted) return;
    setState(() {
      _snapshot = OdometerCaptureSnapshot(
        state: _snapshot.state,
        photoPath: _snapshot.photoPath,
        source: OdometerReadingSource.manual,
        overrideReason: _snapshot.overrideReason,
        outcome: _snapshot.outcome,
      );
    });
    widget.onChanged(_snapshot);
  }

  void _update(OdometerCaptureSnapshot snapshot) {
    if (!mounted) return;
    setState(() => _snapshot = snapshot);
    widget.onChanged(snapshot);
  }

  Future<void> _capture() async {
    final previous = _snapshot;
    _token?.cancel();
    _update(
      OdometerCaptureSnapshot(
        state: OdometerCaptureState.capturing,
        photoPath: previous.photoPath,
        source: previous.source,
        outcome: previous.outcome,
      ),
    );
    final path = await (widget.capturePhoto ?? _defaultCapture)(context);
    if (!mounted) return;
    if (path == null) {
      _update(previous);
      return;
    }
    await _scanPhoto(path);
  }

  Future<void> _scanPhoto(String path) async {
    _token?.cancel();
    final token = OdometerCancellationToken();
    _token = token;
    _update(
      OdometerCaptureSnapshot(
        state: OdometerCaptureState.reviewingCrop,
        photoPath: path,
      ),
    );
    final scanRevision = _editRevision;
    _update(
      OdometerCaptureSnapshot(
        state: OdometerCaptureState.scanning,
        photoPath: path,
      ),
    );

    try {
      final outcome = await (widget.scan ?? _defaultScan)(
        OdometerOcrRequest(
          imagePath: path,
          mode: widget.mode,
          referenceKm: widget.referenceKm,
        ),
        token,
      );
      if (!mounted || token.isCancelled || _snapshot.photoPath != path) return;
      final state = switch (outcome.decision) {
        OdometerOcrDecision.accepted => OdometerCaptureState.accepted,
        OdometerOcrDecision.needsReview => OdometerCaptureState.needsReview,
        OdometerOcrDecision.noReading => OdometerCaptureState.noReading,
      };
      var source = OdometerReadingSource.manual;
      if (outcome.mayPrefill && scanRevision == _editRevision) {
        _applyingOcr = true;
        widget.controller.text = outcome.selectedReadingKm.toString();
        _applyingOcr = false;
        source = OdometerReadingSource.ocrConfirmed;
      }
      _update(
        OdometerCaptureSnapshot(
          state: state,
          photoPath: path,
          source: source,
          outcome: outcome,
        ),
      );
    } catch (_) {
      if (!mounted || token.isCancelled || _snapshot.photoPath != path) return;
      _update(
        OdometerCaptureSnapshot(
          state: OdometerCaptureState.error,
          photoPath: path,
        ),
      );
    }
  }

  void _cancelScan() {
    _token?.cancel();
    _update(
      OdometerCaptureSnapshot(
        state: OdometerCaptureState.noReading,
        photoPath: _snapshot.photoPath,
        source: OdometerReadingSource.manual,
      ),
    );
  }

  Future<String?> _defaultCapture(BuildContext context) async {
    final image = await ImagePicker().pickImage(source: ImageSource.camera);
    if (image == null || !context.mounted) return null;
    final crop = await ImageCropper().cropImage(
      sourcePath: image.path,
      uiSettings: [
        AndroidUiSettings(
          toolbarTitle: 'Fit all digits inside the guide',
          toolbarColor: const Color(0xff0f766e),
          toolbarWidgetColor: Colors.white,
          initAspectRatio: CropAspectRatioPreset.ratio16x9,
          lockAspectRatio: false,
        ),
        IOSUiSettings(title: 'Fit all digits inside the guide'),
      ],
    );
    return crop?.path;
  }

  Future<OdometerOcrOutcome> _defaultScan(
    OdometerOcrRequest request,
    OdometerCancellationToken token,
  ) async => (await OdometerOcrService.readOdometerKm(
    request.imagePath,
    minimumKm: request.referenceKm,
    mode: request.mode,
    cancellationToken: token,
  )).outcome;

  void _chooseCandidate(int reading) {
    _applyingOcr = true;
    widget.controller.text = reading.toString();
    _applyingOcr = false;
    _update(
      OdometerCaptureSnapshot(
        state: _snapshot.state,
        photoPath: _snapshot.photoPath,
        source: OdometerReadingSource.ocrCorrected,
        overrideReason: _snapshot.overrideReason,
        outcome: _snapshot.outcome,
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final outcome = _snapshot.outcome;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Semantics(
          button: true,
          excludeSemantics: true,
          label: _snapshot.photoPath == null
              ? 'Capture odometer photo'
              : 'Retake odometer photo',
          child: InkWell(
            onTap: _snapshot.scanning ? null : _capture,
            borderRadius: BorderRadius.circular(8),
            child: Container(
              height: _snapshot.photoPath == null ? null : 190,
              constraints: const BoxConstraints(minHeight: 190),
              decoration: BoxDecoration(
                color: Colors.white,
                borderRadius: BorderRadius.circular(8),
                border: Border.all(color: const Color(0xff0f766e)),
              ),
              child: _snapshot.photoPath == null
                  ? const _CaptureInstructions()
                  : Stack(
                      fit: StackFit.expand,
                      children: [
                        ClipRRect(
                          borderRadius: BorderRadius.circular(8),
                          child:
                              widget.photoBuilder?.call(
                                context,
                                _snapshot.photoPath!,
                              ) ??
                              Image.file(
                                File(_snapshot.photoPath!),
                                fit: BoxFit.cover,
                              ),
                        ),
                        if (_snapshot.scanning)
                          Positioned(
                            right: 8,
                            bottom: 8,
                            child: FilledButton.tonal(
                              onPressed: _cancelScan,
                              child: const Text('Cancel scan'),
                            ),
                          )
                        else
                          Positioned(
                            right: 8,
                            bottom: 8,
                            child: Wrap(
                              spacing: 8,
                              children: [
                                FilledButton.tonalIcon(
                                  onPressed: () =>
                                      _scanPhoto(_snapshot.photoPath!),
                                  icon: const Icon(Icons.refresh),
                                  label: const Text('Rescan'),
                                ),
                                FilledButton.tonalIcon(
                                  onPressed: _capture,
                                  icon: const Icon(Icons.camera_alt),
                                  label: const Text('Retake'),
                                ),
                              ],
                            ),
                          ),
                      ],
                    ),
            ),
          ),
        ),
        if (_snapshot.state != OdometerCaptureState.idle)
          _OdometerStateMessage(snapshot: _snapshot),
        if (outcome?.decision == OdometerOcrDecision.needsReview &&
            outcome!.candidates.isNotEmpty) ...[
          const SizedBox(height: 8),
          const Text('Choose the digits shown in the photo:'),
          Wrap(
            spacing: 8,
            children: [
              for (final candidate in outcome.candidates.take(3))
                ChoiceChip(
                  label: Text('${candidate.readingKm} KM'),
                  selected:
                      widget.controller.text == candidate.readingKm.toString(),
                  onSelected: (_) => _chooseCandidate(candidate.readingKm),
                ),
            ],
          ),
        ],
        const SizedBox(height: 14),
        TextFormField(
          controller: widget.controller,
          keyboardType: TextInputType.number,
          textInputAction: TextInputAction.done,
          decoration: InputDecoration(
            labelText: widget.mode == OdometerScanMode.start
                ? 'Starting Odometer Reading (KM)*'
                : 'Ending Odometer Reading (KM)*',
            prefixIcon: const Icon(Icons.speed_outlined),
            helperText: widget.mode == OdometerScanMode.start
                ? 'Must be at least ${widget.referenceKm} KM.'
                : 'Must be greater than ${widget.referenceKm} KM.',
          ),
          validator: (value) {
            final parsed = int.tryParse((value ?? '').trim());
            if (parsed == null || parsed <= 0) {
              return 'Enter a positive odometer reading.';
            }
            if (widget.mode == OdometerScanMode.start &&
                parsed < widget.referenceKm) {
              return 'Reading cannot be below the last recorded odometer.';
            }
            if (widget.mode == OdometerScanMode.end &&
                parsed <= widget.referenceKm) {
              return 'Ending KM must be greater than starting KM.';
            }
            return null;
          },
        ),
        if (_snapshot.requiresOverrideReason) ...[
          const SizedBox(height: 10),
          TextFormField(
            decoration: const InputDecoration(
              labelText: 'Exceptional reading reason*',
            ),
            onChanged: (value) => _update(
              OdometerCaptureSnapshot(
                state: _snapshot.state,
                photoPath: _snapshot.photoPath,
                source: _snapshot.source,
                overrideReason: value,
                outcome: _snapshot.outcome,
              ),
            ),
          ),
        ],
        if (_snapshot.photoPath != null && !_snapshot.scanning)
          CheckboxListTile(
            contentPadding: EdgeInsets.zero,
            value: _snapshot.confirmed,
            title: const Text('I verified these digits against the photo.'),
            controlAffinity: ListTileControlAffinity.leading,
            onChanged: widget.controller.text.trim().isEmpty
                ? null
                : (value) => _update(
                    OdometerCaptureSnapshot(
                      state: _snapshot.state,
                      photoPath: _snapshot.photoPath,
                      confirmed: value ?? false,
                      source: _snapshot.source,
                      overrideReason: _snapshot.overrideReason,
                      outcome: _snapshot.outcome,
                    ),
                  ),
          ),
      ],
    );
  }
}

class _CaptureInstructions extends StatelessWidget {
  const _CaptureInstructions();
  @override
  Widget build(BuildContext context) => const Column(
    mainAxisAlignment: MainAxisAlignment.center,
    children: [
      Icon(Icons.photo_camera_outlined, size: 42, color: Color(0xff0f766e)),
      SizedBox(height: 8),
      Text('Capture odometer', style: TextStyle(fontWeight: FontWeight.w900)),
      SizedBox(height: 4),
      Text('Keep all digits horizontal, sharp, and free of glare.'),
    ],
  );
}

class _OdometerStateMessage extends StatelessWidget {
  const _OdometerStateMessage({required this.snapshot});
  final OdometerCaptureSnapshot snapshot;

  @override
  Widget build(BuildContext context) {
    final outcome = snapshot.outcome;
    final (icon, message) = switch (snapshot.state) {
      OdometerCaptureState.capturing => (Icons.photo_camera, 'Opening camera…'),
      OdometerCaptureState.reviewingCrop => (
        Icons.crop,
        'Checking the selected odometer region…',
      ),
      OdometerCaptureState.scanning => (
        Icons.document_scanner,
        'Reading the odometer on this device…',
      ),
      OdometerCaptureState.accepted => (
        Icons.check_circle_outline,
        'Reading found. Verify it against the photo.',
      ),
      OdometerCaptureState.needsReview => (
        Icons.fact_check_outlined,
        'The scan is uncertain. Choose or type the visible digits.',
      ),
      OdometerCaptureState.noReading => (
        Icons.warning_amber,
        'No trustworthy reading found. Retake or enter it manually.',
      ),
      OdometerCaptureState.error => (
        Icons.error_outline,
        'The scan failed. Retake or enter it manually.',
      ),
      OdometerCaptureState.idle => (Icons.info_outline, ''),
    };
    final quality = outcome?.qualityIssues
        .map(OdometerImagePreprocessor.recaptureInstruction)
        .join(' ');
    return Semantics(
      liveRegion: true,
      child: Container(
        margin: const EdgeInsets.only(top: 10),
        padding: const EdgeInsets.all(12),
        decoration: BoxDecoration(
          color: const Color(0xffeef6f4),
          border: Border.all(color: const Color(0xffb7d8cb)),
          borderRadius: BorderRadius.circular(8),
        ),
        child: Row(
          children: [
            if (snapshot.scanning)
              const SizedBox(
                width: 20,
                height: 20,
                child: CircularProgressIndicator(strokeWidth: 2),
              )
            else
              Icon(icon),
            const SizedBox(width: 10),
            Expanded(
              child: Text(
                '$message${quality?.isNotEmpty == true ? ' $quality' : ''}',
              ),
            ),
          ],
        ),
      ),
    );
  }
}
