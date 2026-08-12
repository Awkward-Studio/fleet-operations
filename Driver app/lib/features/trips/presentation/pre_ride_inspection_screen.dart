import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/odometer_ocr_contract.dart';
import '../../../core/providers.dart';
import '../data/trip_providers.dart';
import '../domain/trip.dart';
import 'widgets/odometer_capture_field.dart';

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
  OdometerCaptureSnapshot _odometer = const OdometerCaptureSnapshot();
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

  Future<void> _submit() async {
    if (!_formKey.currentState!.validate()) return;
    if (!_odometer.canSubmit) {
      setState(
        () => _error = 'Capture, verify, and confirm the odometer reading.',
      );
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
          'reading_source': _odometer.source.apiValue,
          'driver_confirmed': _odometer.confirmed.toString(),
          'expected_reference_km': widget.trip.vehicleOdometerKm.toString(),
          'client_version': 'driver-app/1.0.0+1',
          'odometer_override': _odometer.requiresOverrideReason.toString(),
          'odometer_override_reason': _odometer.overrideReason.trim(),
          'client_ocr_decision': ?_odometer.clientDecisionApiValue,
          'idempotency_key':
              'pre-ride-${widget.trip.id}-${DateTime.now().millisecondsSinceEpoch}',
        },
        fileField: 'start_odometer_photo',
        file: File(_odometer.photoPath!),
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
              OdometerCaptureField(
                controller: _odometerController,
                mode: OdometerScanMode.start,
                referenceKm: widget.trip.vehicleOdometerKm,
                onChanged: (snapshot) => setState(() => _odometer = snapshot),
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
                onPressed: _submitting || !_odometer.canSubmit ? null : _submit,
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
