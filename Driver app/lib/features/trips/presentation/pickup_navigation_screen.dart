import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:url_launcher/url_launcher.dart';

import '../../../core/providers.dart';
import '../data/trip_providers.dart';
import '../domain/trip.dart';

class PickupNavigationScreen extends ConsumerStatefulWidget {
  const PickupNavigationScreen({super.key, required this.trip});

  final Trip trip;

  @override
  ConsumerState<PickupNavigationScreen> createState() =>
      _PickupNavigationScreenState();
}

class _PickupNavigationScreenState
    extends ConsumerState<PickupNavigationScreen> {
  bool _arriving = false;
  String? _error;

  Future<void> _launchNavigation() async {
    final uri = _navigationUri(widget.trip);
    if (!await launchUrl(uri, mode: LaunchMode.externalApplication)) {
      setState(() => _error = 'Could not open navigation app.');
    }
  }

  Future<void> _arrivedAtPickup() async {
    setState(() {
      _arriving = true;
      _error = null;
    });

    try {
      final api = ref.read(apiClientProvider);
      await api.post('/fleet/trips/${widget.trip.id}/transition/', {
        'status': TripStatus.arrivedAtPickup.value,
      });
      ref.invalidate(currentDriverTripProvider);
      if (!mounted) return;

      await showModalBottomSheet<bool>(
        context: context,
        isScrollControlled: true,
        useSafeArea: true,
        builder: (_) => GuestOtpVerificationModal(trip: widget.trip),
      );
      if (!mounted) return;
      Navigator.of(context).pop(true);
    } catch (error) {
      setState(() => _error = error.toString().replaceFirst('Exception: ', ''));
    } finally {
      if (mounted) setState(() => _arriving = false);
    }
  }

  Uri _navigationUri(Trip trip) {
    if (trip.hasPickupCoordinates) {
      final lat = trip.pickupLatitude!;
      final lng = trip.pickupLongitude!;
      if (Platform.isIOS) {
        return Uri.parse('http://maps.apple.com/?daddr=$lat,$lng');
      }
      final label = Uri.encodeComponent(trip.pickupCity);
      return Uri.parse('geo:$lat,$lng?q=$lat,$lng($label)');
    }

    final query = Uri.encodeComponent(trip.pickupNavigationLabel);
    if (Platform.isIOS) {
      return Uri.parse('http://maps.apple.com/?daddr=$query');
    }
    return Uri.parse('geo:0,0?q=$query');
  }

  @override
  Widget build(BuildContext context) {
    final trip = widget.trip;

    return Scaffold(
      appBar: AppBar(title: const Text('Pickup Navigation')),
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.fromLTRB(16, 12, 16, 24),
          children: [
            _PickupBanner(trip: trip),
            const SizedBox(height: 16),
            FilledButton.icon(
              onPressed: _launchNavigation,
              icon: const Icon(Icons.navigation),
              label: const Text('Navigate to Pickup'),
              style: FilledButton.styleFrom(
                minimumSize: const Size.fromHeight(52),
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(8),
                ),
              ),
            ),
            const SizedBox(height: 16),
            _CustomerContactCard(trip: trip),
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
              onPressed: _arriving ? null : _arrivedAtPickup,
              icon: _arriving
                  ? const SizedBox(
                      width: 18,
                      height: 18,
                      child: CircularProgressIndicator(strokeWidth: 2),
                    )
                  : const Icon(Icons.location_on),
              label: const Text('I Have Arrived at Pickup Location'),
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
    );
  }
}

class _PickupBanner extends StatelessWidget {
  const _PickupBanner({required this.trip});

  final Trip trip;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: const Color(0xffdde6e2)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                width: 42,
                height: 42,
                decoration: BoxDecoration(
                  color: const Color(0xffe8f3ef),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: const Icon(Icons.map_outlined, color: Color(0xff0f766e)),
              ),
              const SizedBox(width: 12),
              const Expanded(
                child: Text(
                  'Pickup Location',
                  style: TextStyle(fontSize: 20, fontWeight: FontWeight.w900),
                ),
              ),
              const _EtaBadge(),
            ],
          ),
          const SizedBox(height: 16),
          Text(
            trip.pickupAddressLabel,
            style: const TextStyle(
              color: Color(0xff082f2d),
              fontSize: 18,
              fontWeight: FontWeight.w900,
              height: 1.2,
            ),
          ),
          const SizedBox(height: 8),
          Text(
            trip.notes?.trim().isNotEmpty == true
                ? trip.notes!
                : 'Confirm the pickup point with the guest before marking arrival.',
            style: const TextStyle(color: Color(0xff64736f), height: 1.35),
          ),
          if (trip.hasPickupCoordinates) ...[
            const SizedBox(height: 12),
            Text(
              '${trip.pickupLatitude}, ${trip.pickupLongitude}',
              style: const TextStyle(
                color: Color(0xff64736f),
                fontWeight: FontWeight.w700,
              ),
            ),
          ],
        ],
      ),
    );
  }
}

class _EtaBadge extends StatelessWidget {
  const _EtaBadge();

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
      decoration: BoxDecoration(
        color: const Color(0xfffff7ed),
        borderRadius: BorderRadius.circular(999),
      ),
      child: const Text(
        'ETA via Maps',
        style: TextStyle(
          color: Color(0xffb45309),
          fontSize: 12,
          fontWeight: FontWeight.w900,
        ),
      ),
    );
  }
}

class _CustomerContactCard extends StatelessWidget {
  const _CustomerContactCard({required this.trip});

  final Trip trip;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: const Color(0xffdde6e2)),
      ),
      child: Row(
        children: [
          const Icon(Icons.person_outline, color: Color(0xff0f766e)),
          const SizedBox(width: 10),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  trip.customerName,
                  style: const TextStyle(fontWeight: FontWeight.w900),
                ),
                Text(
                  trip.customerPhone.isEmpty
                      ? 'No phone on trip'
                      : trip.customerPhone,
                  style: const TextStyle(color: Color(0xff64736f)),
                ),
              ],
            ),
          ),
          IconButton.filledTonal(
            tooltip: 'Call guest',
            onPressed: trip.customerPhone.isEmpty
                ? null
                : () => launchUrl(Uri(scheme: 'tel', path: trip.customerPhone)),
            icon: const Icon(Icons.call),
          ),
          const SizedBox(width: 8),
          IconButton.filledTonal(
            tooltip: 'SMS guest',
            onPressed: trip.customerPhone.isEmpty
                ? null
                : () => launchUrl(Uri(scheme: 'sms', path: trip.customerPhone)),
            icon: const Icon(Icons.sms_outlined),
          ),
        ],
      ),
    );
  }
}

class GuestOtpVerificationModal extends ConsumerStatefulWidget {
  const GuestOtpVerificationModal({super.key, required this.trip});

  final Trip trip;

  @override
  ConsumerState<GuestOtpVerificationModal> createState() =>
      _GuestOtpVerificationModalState();
}

class _GuestOtpVerificationModalState
    extends ConsumerState<GuestOtpVerificationModal> {
  final _otpController = TextEditingController();
  bool _verifying = false;
  String? _error;

  @override
  void dispose() {
    _otpController.dispose();
    super.dispose();
  }

  Future<void> _verify() async {
    final code = _otpController.text.trim();
    if (code.length < 4) {
      setState(() => _error = 'Enter the guest pickup OTP.');
      return;
    }

    setState(() {
      _verifying = true;
      _error = null;
    });

    try {
      final api = ref.read(apiClientProvider);
      await api.post('/fleet/trips/${widget.trip.id}/verify-otp/', {
        'code': code,
      });
      await api.post('/fleet/trips/${widget.trip.id}/transition/', {
        'status': TripStatus.active.value,
      });
      ref.invalidate(currentDriverTripProvider);
      if (!mounted) return;
      Navigator.of(context).pop(true);
    } catch (error) {
      setState(() => _error = error.toString().replaceFirst('Exception: ', ''));
    } finally {
      if (mounted) setState(() => _verifying = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: EdgeInsets.fromLTRB(
        20,
        20,
        20,
        MediaQuery.of(context).viewInsets.bottom + 20,
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          const Text(
            'Verify Guest OTP',
            style: TextStyle(fontSize: 22, fontWeight: FontWeight.w900),
          ),
          const SizedBox(height: 6),
          Text(
            'Ask ${widget.trip.customerName} for the pickup OTP before starting the active ride.',
            style: const TextStyle(color: Color(0xff64736f), height: 1.35),
          ),
          const SizedBox(height: 16),
          TextField(
            controller: _otpController,
            autofocus: true,
            keyboardType: TextInputType.number,
            maxLength: 6,
            textInputAction: TextInputAction.done,
            onSubmitted: (_) => _verify(),
            decoration: InputDecoration(
              labelText: 'Pickup OTP',
              counterText: '',
              prefixIcon: const Icon(Icons.password),
              errorText: _error,
            ),
          ),
          const SizedBox(height: 16),
          FilledButton.icon(
            onPressed: _verifying ? null : _verify,
            icon: _verifying
                ? const SizedBox(
                    width: 18,
                    height: 18,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  )
                : const Icon(Icons.verified_user_outlined),
            label: const Text('Verify & Start Active Trip'),
            style: FilledButton.styleFrom(
              minimumSize: const Size.fromHeight(50),
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(8),
              ),
            ),
          ),
        ],
      ),
    );
  }
}
