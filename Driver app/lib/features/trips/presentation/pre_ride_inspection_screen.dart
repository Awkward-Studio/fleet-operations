import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:image_picker/image_picker.dart';

import '../../../core/providers.dart';
import '../data/trip_providers.dart';
import '../domain/trip.dart';

class PreRideInspectionScreen extends ConsumerStatefulWidget {
  const PreRideInspectionScreen({super.key, required this.trip});

  final Trip trip;

  @override
  ConsumerState<PreRideInspectionScreen> createState() =>
      _PreRideInspectionScreenState();
}

class _PreRideInspectionScreenState
    extends ConsumerState<PreRideInspectionScreen> {
  final _formKey = GlobalKey<FormState>();
  final _odometerController = TextEditingController();
  final _picker = ImagePicker();
  XFile? _odometerPhoto;
  bool _cleanlinessOk = true;
  bool _fuelLevelOk = true;
  bool _tirePressureOk = true;
  bool _submitting = false;
  String? _error;

  @override
  void dispose() {
    _odometerController.dispose();
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
      setState(() => _error = 'Capture the starting odometer photo.');
      return;
    }

    setState(() {
      _submitting = true;
      _error = null;
    });

    try {
      final api = ref.read(apiClientProvider);
      await api.postMultipart(
        '/fleet/trips/${widget.trip.id}/checklist/',
        fields: {
          'start_odometer_km': _odometerController.text.trim(),
          'cleanliness_ok': _cleanlinessOk.toString(),
          'fuel_level_percent': _fuelLevelOk ? '75' : '25',
          'tire_pressure_ok': _tirePressureOk.toString(),
          'notes': 'Submitted from driver mobile pre-ride inspection.',
          'idempotency_key':
              'pre-ride-${widget.trip.id}-${DateTime.now().millisecondsSinceEpoch}',
        },
        fileField: 'start_odometer_photo',
        file: File(_odometerPhoto!.path),
      );

      ref.invalidate(currentDriverTripProvider);
      if (!mounted) return;
      Navigator.of(context).pop(true);
    } catch (error) {
      setState(() => _error = error.toString().replaceFirst('Exception: ', ''));
    } finally {
      if (mounted) setState(() => _submitting = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Pre-Ride Inspection')),
      body: SafeArea(
        child: Form(
          key: _formKey,
          child: ListView(
            padding: const EdgeInsets.fromLTRB(16, 12, 16, 24),
            children: [
              const Text(
                'Capture Starting Odometer Photo',
                style: TextStyle(fontSize: 20, fontWeight: FontWeight.w900),
              ),
              const SizedBox(height: 12),
              _PhotoCaptureCard(
                photo: _odometerPhoto,
                onCapture: _capturePhoto,
              ),
              const SizedBox(height: 18),
              TextFormField(
                controller: _odometerController,
                keyboardType: TextInputType.number,
                textInputAction: TextInputAction.done,
                decoration: InputDecoration(
                  labelText: 'Odometer Reading (KM)*',
                  hintText: 'e.g. ${widget.trip.vehicleOdometerKm}',
                  prefixIcon: const Icon(Icons.speed_outlined),
                  helperText:
                      'Must be at least ${widget.trip.vehicleOdometerKm} KM.',
                ),
                validator: (value) {
                  final parsed = int.tryParse((value ?? '').trim());
                  if (parsed == null || parsed <= 0) {
                    return 'Enter a positive odometer reading.';
                  }
                  if (parsed < widget.trip.vehicleOdometerKm) {
                    return 'Reading cannot be below last recorded odometer.';
                  }
                  return null;
                },
              ),
              const SizedBox(height: 22),
              const Text(
                'Vehicle Checklist',
                style: TextStyle(fontSize: 20, fontWeight: FontWeight.w900),
              ),
              const SizedBox(height: 8),
              _ChecklistSwitch(
                title: 'Clean Interior & Exterior',
                value: _cleanlinessOk,
                onChanged: (value) => setState(() => _cleanlinessOk = value),
              ),
              _ChecklistSwitch(
                title: 'Fuel / Battery Level > 50%',
                value: _fuelLevelOk,
                onChanged: (value) => setState(() => _fuelLevelOk = value),
              ),
              _ChecklistSwitch(
                title: 'Tire Pressure Normal',
                value: _tirePressureOk,
                onChanged: (value) => setState(() => _tirePressureOk = value),
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
                    : const Icon(Icons.route),
                label: const Text('Submit & Start En Route to Pickup'),
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
                    'Capture the starting odometer clearly.',
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

class _ChecklistSwitch extends StatelessWidget {
  const _ChecklistSwitch({
    required this.title,
    required this.value,
    required this.onChanged,
  });

  final String title;
  final bool value;
  final ValueChanged<bool> onChanged;

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.only(top: 10),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: const Color(0xffdde6e2)),
      ),
      child: SwitchListTile(
        value: value,
        onChanged: onChanged,
        title: Text(title, style: const TextStyle(fontWeight: FontWeight.w800)),
        secondary: Icon(
          value ? Icons.check_circle : Icons.error_outline,
          color: value ? const Color(0xff0f766e) : const Color(0xffb45309),
        ),
      ),
    );
  }
}
