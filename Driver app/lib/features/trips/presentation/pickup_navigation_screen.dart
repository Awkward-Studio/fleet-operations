import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:url_launcher/url_launcher.dart';

import '../../../core/location_tracking_service.dart';
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
      String? localOtpCode;
      if (widget.trip.otpMode.isLocal) {
        final generated = await api.post(
          '/fleet/trips/${widget.trip.id}/generate-otp/',
          {'digits': 4},
        );
        if (generated is Map<String, dynamic>) {
          localOtpCode = generated['code'] as String?;
        }
      }
      ref.invalidate(currentDriverTripProvider);
      if (!mounted) return;

      await showModalBottomSheet<bool>(
        context: context,
        isScrollControlled: true,
        useSafeArea: true,
        builder: (_) => GuestOtpVerificationModal(
          trip: widget.trip,
          initialLocalOtpCode: localOtpCode,
        ),
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
                child: const Icon(Icons.navigation, color: Color(0xff082f2d)),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'Ride #${trip.id}',
                      style: const TextStyle(
                        fontWeight: FontWeight.w800,
                        fontSize: 16,
                      ),
                    ),
                    Text(
                      '${trip.pickupCity} to ${trip.dropCity}',
                      style: const TextStyle(color: Color(0xff64736f)),
                    ),
                  ],
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
  const GuestOtpVerificationModal({
    super.key,
    required this.trip,
    this.initialLocalOtpCode,
  });

  final Trip trip;
  final String? initialLocalOtpCode;

  @override
  ConsumerState<GuestOtpVerificationModal> createState() =>
      _GuestOtpVerificationModalState();
}

class _GuestOtpVerificationModalState
    extends ConsumerState<GuestOtpVerificationModal> {
  late final List<TextEditingController> _digitControllers;
  late final List<FocusNode> _digitFocusNodes;
  bool _verifying = false;
  bool _resending = false;
  String? _error;
  String? _localOtpCode;
  String? _notice;

  bool get _isLocalOtp => widget.trip.otpMode.isLocal;
  int get _visibleDigits => _isLocalOtp ? 4 : 6;

  @override
  void initState() {
    super.initState();
    _localOtpCode = widget.initialLocalOtpCode;
    _digitControllers = List.generate(6, (_) => TextEditingController());
    _digitFocusNodes = List.generate(6, (_) => FocusNode());

    if (_localOtpCode != null) {
      _applyOtpCode(_localOtpCode!);
    } else if (_isLocalOtp) {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        _resendLocalOtp();
      });
    }
  }

  void _applyOtpCode(String code) {
    final chars = code.trim().split('');
    for (var i = 0; i < chars.length && i < _digitControllers.length; i++) {
      _digitControllers[i].text = chars[i];
    }
  }

  @override
  void dispose() {
    for (final controller in _digitControllers) {
      controller.dispose();
    }
    for (final node in _digitFocusNodes) {
      node.dispose();
    }
    super.dispose();
  }

  String get _code => _digitControllers
      .take(_visibleDigits)
      .map((controller) => controller.text.trim())
      .join();

  Future<void> _verify() async {
    final code = _code;
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
        'otp_code': code,
      });
      await LocationTrackingService.startAfterOtpSuccess(widget.trip);
      ref.invalidate(currentDriverTripProvider);
      if (!mounted) return;
      Navigator.of(context).pop(true);
    } catch (error) {
      setState(() => _error = error.toString().replaceFirst('Exception: ', ''));
    } finally {
      if (mounted) setState(() => _verifying = false);
    }
  }

  Future<void> _resendLocalOtp() async {
    if (!_isLocalOtp) return;

    setState(() {
      _resending = true;
      _error = null;
      _notice = null;
    });

    try {
      final api = ref.read(apiClientProvider);
      final generated = await api.post(
        '/fleet/trips/${widget.trip.id}/generate-otp/',
        {'digits': 4},
      );
      final code = generated is Map<String, dynamic>
          ? generated['code'] as String?
          : null;
      setState(() {
        _localOtpCode = code;
        _notice = 'Local OTP generated for testing.';
      });
      if (code != null) {
        _applyOtpCode(code);
      }
    } catch (error) {
      setState(() => _error = error.toString().replaceFirst('Exception: ', ''));
    } finally {
      if (mounted) setState(() => _resending = false);
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
            _isLocalOtp
                ? 'Use the local fleet OTP for ${widget.trip.customerName}.'
                : 'Ask ${widget.trip.customerName} for the MMT pickup OTP.',
            style: const TextStyle(color: Color(0xff64736f), height: 1.35),
          ),
          const SizedBox(height: 10),
          _OtpModePill(label: widget.trip.otpMode.label),
          if (_isLocalOtp && _localOtpCode != null) ...[
            const SizedBox(height: 12),
            _LocalOtpPreview(code: _localOtpCode!),
          ],
          const SizedBox(height: 16),
          _OtpDigitInput(
            controllers: _digitControllers,
            focusNodes: _digitFocusNodes,
            visibleDigits: _visibleDigits,
            hasError: _error != null,
            onCompleted: _verify,
          ),
          if (_error != null) ...[
            const SizedBox(height: 8),
            Text(
              _error!,
              style: const TextStyle(
                color: Color(0xff9f1d14),
                fontWeight: FontWeight.w700,
              ),
            ),
          ],
          if (_notice != null) ...[
            const SizedBox(height: 8),
            Text(
              _notice!,
              style: const TextStyle(
                color: Color(0xff0f766e),
                fontWeight: FontWeight.w700,
              ),
            ),
          ],
          if (_isLocalOtp) ...[
            const SizedBox(height: 12),
            TextButton.icon(
              onPressed: _resending ? null : _resendLocalOtp,
              icon: _resending
                  ? const SizedBox(
                      width: 16,
                      height: 16,
                      child: CircularProgressIndicator(strokeWidth: 2),
                    )
                  : const Icon(Icons.refresh),
              label: const Text('Resend OTP'),
            ),
          ],
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

class _OtpModePill extends StatelessWidget {
  const _OtpModePill({required this.label});

  final String label;

  @override
  Widget build(BuildContext context) {
    return Align(
      alignment: Alignment.centerLeft,
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
        decoration: BoxDecoration(
          color: const Color(0xffe8f3ef),
          borderRadius: BorderRadius.circular(999),
        ),
        child: Text(
          label,
          style: const TextStyle(
            color: Color(0xff0f766e),
            fontSize: 12,
            fontWeight: FontWeight.w900,
          ),
        ),
      ),
    );
  }
}

class _LocalOtpPreview extends StatelessWidget {
  const _LocalOtpPreview({required this.code});

  final String code;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: const Color(0xfffff7ed),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: const Color(0xffffedd5)),
      ),
      child: Row(
        children: [
          const Icon(Icons.key, color: Color(0xffb45309)),
          const SizedBox(width: 10),
          Expanded(
            child: Text(
              '🔑 TESTING PICKUP OTP: $code (AUTO-FILLED)',
              style: const TextStyle(
                color: Color(0xff7c2d12),
                fontWeight: FontWeight.w900,
                fontSize: 13,
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _OtpDigitInput extends StatelessWidget {
  const _OtpDigitInput({
    required this.controllers,
    required this.focusNodes,
    required this.visibleDigits,
    required this.hasError,
    required this.onCompleted,
  });

  final List<TextEditingController> controllers;
  final List<FocusNode> focusNodes;
  final int visibleDigits;
  final bool hasError;
  final VoidCallback onCompleted;

  @override
  Widget build(BuildContext context) {
    return Row(
      children: List.generate(visibleDigits, (index) {
        return Expanded(
          child: Padding(
            padding: EdgeInsets.only(right: index == visibleDigits - 1 ? 0 : 8),
            child: TextField(
              controller: controllers[index],
              focusNode: focusNodes[index],
              autofocus: index == 0,
              keyboardType: TextInputType.number,
              textAlign: TextAlign.center,
              maxLength: 1,
              style: const TextStyle(fontSize: 22, fontWeight: FontWeight.w900),
              decoration: InputDecoration(
                counterText: '',
                filled: true,
                fillColor: hasError
                    ? const Color(0xfffff1f0)
                    : const Color(0xfff6f8f7),
                enabledBorder: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(8),
                  borderSide: BorderSide(
                    color: hasError
                        ? const Color(0xffe11d48)
                        : const Color(0xffdde6e2),
                  ),
                ),
              ),
              onChanged: (value) {
                if (value.isNotEmpty && index < visibleDigits - 1) {
                  focusNodes[index + 1].requestFocus();
                }
                if (value.isNotEmpty && index == visibleDigits - 1) {
                  FocusScope.of(context).unfocus();
                  onCompleted();
                }
                if (value.isEmpty && index > 0) {
                  focusNodes[index - 1].requestFocus();
                }
              },
            ),
          ),
        );
      }),
    );
  }
}
