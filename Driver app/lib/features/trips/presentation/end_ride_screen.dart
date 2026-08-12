import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/location_tracking_service.dart';
import '../../../core/odometer_ocr_contract.dart';
import '../../../core/providers.dart';
import '../data/trip_providers.dart';
import '../domain/trip.dart';
import 'widgets/odometer_capture_field.dart';

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
  OdometerCaptureSnapshot _odometer = const OdometerCaptureSnapshot();
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
  void dispose() {
    _endingOdometerController.dispose();
    _notesController.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    if (!_formKey.currentState!.validate()) return;
    if (_startOdometerKm == null) {
      setState(
        () => _error = 'Starting odometer is missing. Complete pre-ride first.',
      );
      return;
    }
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
        '/fleet/trips/${widget.trip.id}/complete/',
        fields: {
          'end_odometer_km': _endingOdometerController.text.trim(),
          'notes': _notesController.text.trim(),
          'reading_source': _odometer.source.apiValue,
          'driver_confirmed': _odometer.confirmed.toString(),
          'expected_reference_km': _startOdometerKm.toString(),
          'client_version': 'driver-app/1.0.0+1',
          'odometer_override': _odometer.requiresOverrideReason.toString(),
          'odometer_override_reason': _odometer.overrideReason.trim(),
          'client_ocr_decision': ?_odometer.clientDecisionApiValue,
          'idempotency_key':
              'end-ride-${widget.trip.id}-${DateTime.now().millisecondsSinceEpoch}',
        },
        fileField: 'end_odometer_photo',
        file: File(_odometer.photoPath!),
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
              if (startOdometer == null)
                const Card(
                  child: Padding(
                    padding: EdgeInsets.all(12),
                    child: Text(
                      'Starting odometer is missing. Complete the pre-ride inspection before ending this trip.',
                    ),
                  ),
                ),
              OdometerCaptureField(
                controller: _endingOdometerController,
                mode: OdometerScanMode.end,
                referenceKm: startOdometer ?? widget.trip.vehicleOdometerKm,
                onChanged: (snapshot) => setState(() => _odometer = snapshot),
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
                onPressed:
                    _submitting || !_odometer.canSubmit || startOdometer == null
                    ? null
                    : _submit,
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
