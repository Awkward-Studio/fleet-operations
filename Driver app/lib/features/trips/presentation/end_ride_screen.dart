import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:image_picker/image_picker.dart';

import '../../../core/location_tracking_service.dart';
import '../../../core/providers.dart';
import '../data/trip_providers.dart';
import '../domain/trip.dart';

class EndRideScreen extends ConsumerStatefulWidget {
  const EndRideScreen({super.key, required this.trip});

  final Trip trip;

  @override
  ConsumerState<EndRideScreen> createState() => _EndRideScreenState();
}

class _EndRideScreenState extends ConsumerState<EndRideScreen> {
  final _formKey = GlobalKey<FormState>();
  final _endingOdometerController = TextEditingController();
  final _notesController = TextEditingController();
  final _picker = ImagePicker();
  XFile? _odometerPhoto;
  bool _submitting = false;
  String? _error;

  int? get _startOdometerKm => widget.trip.startOdometerKm;

  int? get _endingOdometerKm =>
      int.tryParse(_endingOdometerController.text.trim());

  int? get _calculatedDistance {
    final start = _startOdometerKm;
    final end = _endingOdometerKm;
    if (start == null || end == null || end <= start) return null;
    return end - start;
  }

  @override
  void initState() {
    super.initState();
    final minimum = (_startOdometerKm ?? widget.trip.vehicleOdometerKm) + 1;
    _endingOdometerController.text = minimum.toString();
  }

  @override
  void dispose() {
    _endingOdometerController.dispose();
    _notesController.dispose();
    super.dispose();
  }

  Future<void> _capturePhoto() async {
    final image = await _picker.pickImage(
      source: ImageSource.camera,
      imageQuality: 85,
      maxWidth: 1600,
    );
    if (image == null) return;
    setState(() {
      _odometerPhoto = image;
      _error = null;
    });
  }

  Future<void> _submit() async {
    if (!_formKey.currentState!.validate()) return;
    if (_odometerPhoto == null) {
      setState(() => _error = 'Capture the ending odometer photo.');
      return;
    }

    setState(() {
      _submitting = true;
      _error = null;
    });

    try {
      final api = ref.read(apiClientProvider);
      await api.postMultipart(
        '/fleet/trips/${widget.trip.id}/complete/',
        fields: {
          'end_odometer_km': _endingOdometerController.text.trim(),
          'notes': _notesController.text.trim(),
          'idempotency_key':
              'end-ride-${widget.trip.id}-${DateTime.now().millisecondsSinceEpoch}',
        },
        fileField: 'end_odometer_photo',
        file: File(_odometerPhoto!.path),
      );

      await LocationTrackingService.stop();
      ref.invalidate(currentDriverTripProvider);
      if (!mounted) return;

      await _showCompletionSummary();
      if (!mounted) return;
      Navigator.of(context).pop(true);
    } catch (error) {
      setState(() => _error = error.toString().replaceFirst('Exception: ', ''));
    } finally {
      if (mounted) setState(() => _submitting = false);
    }
  }

  Future<void> _showCompletionSummary() {
    return showDialog<void>(
      context: context,
      barrierDismissible: false,
      builder: (context) => AlertDialog(
        title: const Text('Trip Completed'),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            _SummaryLine(label: 'Drop city', value: widget.trip.dropCity),
            _SummaryLine(
              label: 'Starting KM',
              value: '${_startOdometerKm ?? 0}',
            ),
            _SummaryLine(
              label: 'Ending KM',
              value: _endingOdometerController.text.trim(),
            ),
            _SummaryLine(
              label: 'Distance',
              value: '${_calculatedDistance ?? 0} KM',
            ),
          ],
        ),
        actions: [
          FilledButton(
            onPressed: () => Navigator.of(context).pop(),
            child: const Text('Back to Dashboard'),
          ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final startOdometer = _startOdometerKm;
    final distance = _calculatedDistance;

    return Scaffold(
      appBar: AppBar(title: const Text('End Ride')),
      body: SafeArea(
        child: Form(
          key: _formKey,
          child: ListView(
            padding: const EdgeInsets.fromLTRB(16, 12, 16, 24),
            children: [
              const Text(
                'End Ride & Final Odometer Audit',
                style: TextStyle(fontSize: 22, fontWeight: FontWeight.w900),
              ),
              const SizedBox(height: 16),
              const Text(
                'Capture Ending Odometer Photo',
                style: TextStyle(fontSize: 18, fontWeight: FontWeight.w900),
              ),
              const SizedBox(height: 12),
              _PhotoCaptureCard(
                photo: _odometerPhoto,
                onCapture: _capturePhoto,
              ),
              const SizedBox(height: 18),
              TextFormField(
                controller: _endingOdometerController,
                keyboardType: TextInputType.number,
                textInputAction: TextInputAction.next,
                onChanged: (_) => setState(() {}),
                decoration: InputDecoration(
                  labelText: 'Ending Odometer Reading (KM)*',
                  hintText: startOdometer == null
                      ? 'Enter ending KM'
                      : 'Must be greater than $startOdometer',
                  prefixIcon: const Icon(Icons.speed_outlined),
                ),
                validator: (value) {
                  final parsed = int.tryParse((value ?? '').trim());
                  if (parsed == null || parsed <= 0) {
                    return 'Enter a positive odometer reading.';
                  }
                  if (startOdometer == null) {
                    return 'Starting odometer is missing. Submit pre-ride inspection first.';
                  }
                  if (parsed <= startOdometer) {
                    return 'Ending KM must be greater than starting KM.';
                  }
                  return null;
                },
              ),
              const SizedBox(height: 16),
              _DistanceAuditCard(
                startOdometerKm: startOdometer,
                endingOdometerKm: _endingOdometerKm,
                calculatedDistanceKm: distance,
              ),
              const SizedBox(height: 16),
              TextFormField(
                controller: _notesController,
                minLines: 2,
                maxLines: 4,
                decoration: const InputDecoration(
                  labelText: 'Final notes',
                  prefixIcon: Icon(Icons.notes_outlined),
                ),
              ),
              if (_error != null) ...[
                const SizedBox(height: 14),
                Container(
                  padding: const EdgeInsets.all(12),
                  decoration: BoxDecoration(
                    color: const Color(0xfffff1f0),
                    borderRadius: BorderRadius.circular(8),
                    border: Border.all(color: const Color(0xffffcdc7)),
                  ),
                  child: Text(
                    _error!,
                    style: const TextStyle(color: Color(0xff9f1d14)),
                  ),
                ),
              ],
              const SizedBox(height: 22),
              FilledButton.icon(
                onPressed: _submitting ? null : _submit,
                icon: _submitting
                    ? const SizedBox(
                        width: 18,
                        height: 18,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      )
                    : const Icon(Icons.flag_circle_outlined),
                label: const Text('Confirm & Complete Trip'),
                style: FilledButton.styleFrom(
                  minimumSize: const Size.fromHeight(52),
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(8),
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _PhotoCaptureCard extends StatelessWidget {
  const _PhotoCaptureCard({required this.photo, required this.onCapture});

  final XFile? photo;
  final VoidCallback onCapture;

  @override
  Widget build(BuildContext context) {
    return InkWell(
      onTap: onCapture,
      borderRadius: BorderRadius.circular(8),
      child: Container(
        height: 190,
        decoration: BoxDecoration(
          color: Colors.white,
          borderRadius: BorderRadius.circular(8),
          border: Border.all(
            color: photo == null
                ? const Color(0xffd8e0dd)
                : const Color(0xff0f766e),
            width: photo == null ? 1 : 1.4,
          ),
        ),
        child: photo == null
            ? const Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Icon(
                    Icons.photo_camera_outlined,
                    size: 42,
                    color: Color(0xff0f766e),
                  ),
                  SizedBox(height: 10),
                  Text(
                    'Tap to open camera',
                    style: TextStyle(fontWeight: FontWeight.w900),
                  ),
                  SizedBox(height: 4),
                  Text(
                    'Capture the ending odometer clearly.',
                    style: TextStyle(color: Color(0xff64736f)),
                  ),
                ],
              )
            : Stack(
                fit: StackFit.expand,
                children: [
                  ClipRRect(
                    borderRadius: BorderRadius.circular(8),
                    child: Image.file(File(photo!.path), fit: BoxFit.cover),
                  ),
                  Positioned(
                    right: 10,
                    bottom: 10,
                    child: FilledButton.tonalIcon(
                      onPressed: onCapture,
                      icon: const Icon(Icons.camera_alt),
                      label: const Text('Retake Photo'),
                    ),
                  ),
                ],
              ),
      ),
    );
  }
}

class _DistanceAuditCard extends StatelessWidget {
  const _DistanceAuditCard({
    required this.startOdometerKm,
    required this.endingOdometerKm,
    required this.calculatedDistanceKm,
  });

  final int? startOdometerKm;
  final int? endingOdometerKm;
  final int? calculatedDistanceKm;

  @override
  Widget build(BuildContext context) {
    final valid = calculatedDistanceKm != null;
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: valid ? const Color(0xffe8f3ef) : const Color(0xfffff7ed),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(
          color: valid ? const Color(0xffb7d8cb) : const Color(0xffffedd5),
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            valid
                ? 'Distance Calculated: $calculatedDistanceKm KM'
                : 'Distance will calculate after a valid ending KM.',
            style: TextStyle(
              color: valid ? const Color(0xff0f5132) : const Color(0xff7c2d12),
              fontWeight: FontWeight.w900,
            ),
          ),
          const SizedBox(height: 6),
          Text(
            'Starting Odometer: ${startOdometerKm ?? '--'} KM',
            style: const TextStyle(color: Color(0xff64736f)),
          ),
          Text(
            'Ending Odometer: ${endingOdometerKm ?? '--'} KM',
            style: const TextStyle(color: Color(0xff64736f)),
          ),
        ],
      ),
    );
  }
}

class _SummaryLine extends StatelessWidget {
  const _SummaryLine({required this.label, required this.value});

  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: Row(
        children: [
          Expanded(
            child: Text(
              label,
              style: const TextStyle(color: Color(0xff64736f)),
            ),
          ),
          Text(value, style: const TextStyle(fontWeight: FontWeight.w900)),
        ],
      ),
    );
  }
}
