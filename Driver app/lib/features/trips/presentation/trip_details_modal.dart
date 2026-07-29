import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:url_launcher/url_launcher.dart';

import '../data/trip_providers.dart';
import '../domain/trip.dart';
import 'end_ride_screen.dart';

class TripDetailsModal extends ConsumerWidget {
  const TripDetailsModal({super.key, required this.trip});

  final Trip trip;

  Future<void> _callCustomer(BuildContext context) async {
    final phone = trip.customerPhone.trim();
    if (phone.isEmpty) return;
    final uri = Uri.parse('tel:$phone');
    if (!await launchUrl(uri)) {
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Could not dial $phone')),
        );
      }
    }
  }

  Future<void> _launchDropNavigation(BuildContext context) async {
    final destination = Uri.encodeComponent(
      trip.dropAddress.trim().isNotEmpty ? trip.dropAddress : trip.dropCity,
    );
    final uri = Platform.isIOS
        ? Uri.parse('http://maps.apple.com/?daddr=$destination')
        : Uri.parse('geo:0,0?q=$destination');

    if (!await launchUrl(uri, mode: LaunchMode.externalApplication)) {
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Could not launch maps application')),
        );
      }
    }
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final isTripActive = trip.status == TripStatus.active;

    return DraggableScrollableSheet(
      initialChildSize: 0.85,
      minChildSize: 0.5,
      maxChildSize: 0.95,
      expand: false,
      builder: (context, scrollController) {
        return Container(
          decoration: const BoxDecoration(
            color: Colors.white,
            borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
          ),
          child: Column(
            children: [
              // Handle Bar
              Center(
                child: Container(
                  margin: const EdgeInsets.only(top: 12, bottom: 8),
                  width: 40,
                  height: 4,
                  decoration: BoxDecoration(
                    color: const Color(0xffd1d5db),
                    borderRadius: BorderRadius.circular(2),
                  ),
                ),
              ),
              // Header
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 12),
                child: Row(
                  children: [
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            'Trip #${trip.id}',
                            style: const TextStyle(
                              fontSize: 22,
                              fontWeight: FontWeight.w900,
                              color: Color(0xff111827),
                            ),
                          ),
                          if (trip.otaSource.isNotEmpty)
                            Text(
                              'Source: ${trip.otaSource.toUpperCase()}',
                              style: const TextStyle(
                                fontSize: 13,
                                color: Color(0xff6b7280),
                                fontWeight: FontWeight.w600,
                              ),
                            ),
                        ],
                      ),
                    ),
                    _StatusBadge(status: trip.status),
                  ],
                ),
              ),
              const Divider(height: 1),

              // Content Body
              Expanded(
                child: ListView(
                  controller: scrollController,
                  padding: const EdgeInsets.all(20),
                  children: [
                    // Guest Card
                    Container(
                      padding: const EdgeInsets.all(16),
                      decoration: BoxDecoration(
                        color: const Color(0xfff9fafb),
                        borderRadius: BorderRadius.circular(12),
                        border: Border.all(color: const Color(0xffe5e7eb)),
                      ),
                      child: Row(
                        children: [
                          const CircleAvatar(
                            radius: 22,
                            backgroundColor: Color(0xff0f766e),
                            child: Icon(Icons.person, color: Colors.white, size: 24),
                          ),
                          const SizedBox(width: 14),
                          Expanded(
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Text(
                                  trip.customerName,
                                  style: const TextStyle(
                                    fontSize: 16,
                                    fontWeight: FontWeight.bold,
                                    color: Color(0xff111827),
                                  ),
                                ),
                                if (trip.customerPhone.isNotEmpty)
                                  Text(
                                    trip.customerPhone,
                                    style: const TextStyle(
                                      fontSize: 14,
                                      color: Color(0xff4b5563),
                                    ),
                                  ),
                              ],
                            ),
                          ),
                          if (trip.customerPhone.isNotEmpty)
                            IconButton.filledTonal(
                              onPressed: () => _callCustomer(context),
                              icon: const Icon(Icons.phone),
                              style: IconButton.styleFrom(
                                backgroundColor: const Color(0xffccfbf1),
                                foregroundColor: const Color(0xff0f766e),
                              ),
                            ),
                        ],
                      ),
                    ),

                    const SizedBox(height: 20),

                    // Route Card
                    const Text(
                      'ROUTE DETAILS',
                      style: TextStyle(
                        fontSize: 12,
                        fontWeight: FontWeight.w800,
                        letterSpacing: 1.1,
                        color: Color(0xff6b7280),
                      ),
                    ),
                    const SizedBox(height: 10),
                    Container(
                      padding: const EdgeInsets.all(16),
                      decoration: BoxDecoration(
                        color: Colors.white,
                        borderRadius: BorderRadius.circular(12),
                        border: Border.all(color: const Color(0xffe5e7eb)),
                      ),
                      child: Column(
                        children: [
                          _LocationRow(
                            icon: Icons.radio_button_checked,
                            iconColor: const Color(0xff10b981),
                            title: 'Pickup Location',
                            city: trip.pickupCity,
                            address: trip.pickupAddressLabel,
                            time: trip.pickupAt != null
                                ? '${trip.pickupAt!.hour.toString().padLeft(2, '0')}:${trip.pickupAt!.minute.toString().padLeft(2, '0')}'
                                : null,
                          ),
                          const Padding(
                            padding: EdgeInsets.only(left: 11, top: 4, bottom: 4),
                            child: Align(
                              alignment: Alignment.centerLeft,
                              child: SizedBox(
                                height: 24,
                                child: VerticalDivider(
                                  width: 2,
                                  thickness: 2,
                                  color: Color(0xffd1d5db),
                                ),
                              ),
                            ),
                          ),
                          _LocationRow(
                            icon: Icons.location_on,
                            iconColor: const Color(0xffef4444),
                            title: 'Dropoff Destination',
                            city: trip.dropCity,
                            address: trip.dropAddressLabel,
                            time: trip.estimatedDropAt != null
                                ? '${trip.estimatedDropAt!.hour.toString().padLeft(2, '0')}:${trip.estimatedDropAt!.minute.toString().padLeft(2, '0')}'
                                : null,
                          ),
                          const SizedBox(height: 14),
                          OutlinedButton.icon(
                            onPressed: () => _launchDropNavigation(context),
                            icon: const Icon(Icons.navigation, size: 18),
                            label: const Text('Navigate to Dropoff Location'),
                            style: OutlinedButton.styleFrom(
                              minimumSize: const Size.fromHeight(44),
                              foregroundColor: const Color(0xff0f766e),
                              side: const BorderSide(color: Color(0xff0f766e)),
                              shape: RoundedRectangleBorder(
                                borderRadius: BorderRadius.circular(8),
                              ),
                            ),
                          ),
                        ],
                      ),
                    ),

                    const SizedBox(height: 20),

                    // Vehicle & Trip Info Card
                    const Text(
                      'TRIP & VEHICLE INFO',
                      style: TextStyle(
                        fontSize: 12,
                        fontWeight: FontWeight.w800,
                        letterSpacing: 1.1,
                        color: Color(0xff6b7280),
                      ),
                    ),
                    const SizedBox(height: 10),
                    Container(
                      padding: const EdgeInsets.all(16),
                      decoration: BoxDecoration(
                        color: const Color(0xfff9fafb),
                        borderRadius: BorderRadius.circular(12),
                        border: Border.all(color: const Color(0xffe5e7eb)),
                      ),
                      child: Column(
                        children: [
                          if (trip.vehicleLabel != null)
                            _DetailRow(
                              icon: Icons.directions_car,
                              label: 'Assigned Vehicle',
                              value: trip.vehicleLabel!,
                            ),
                          _DetailRow(
                            icon: Icons.speed,
                            label: 'Start Odometer Reading',
                            value: trip.startOdometerKm != null
                                ? '${trip.startOdometerKm} km'
                                : '${trip.vehicleOdometerKm} km (Initial)',
                          ),
                          _DetailRow(
                            icon: Icons.security,
                            label: 'OTP Security',
                            value: '${trip.otpMode.label} (Verified)',
                            valueColor: const Color(0xff059669),
                          ),
                          if (trip.notes != null && trip.notes!.isNotEmpty)
                            _DetailRow(
                              icon: Icons.note,
                              label: 'Special Instructions',
                              value: trip.notes!,
                            ),
                        ],
                      ),
                    ),
                  ],
                ),
              ),

              // Bottom Action Button
              Padding(
                padding: const EdgeInsets.all(16),
                child: isTripActive
                    ? FilledButton.icon(
                        onPressed: () async {
                          Navigator.of(context).pop();
                          final completed = await Navigator.of(context).push<bool>(
                            MaterialPageRoute(
                              builder: (_) => EndRideScreen(trip: trip),
                            ),
                          );
                          if (completed == true) {
                            ref.invalidate(currentDriverTripProvider);
                          }
                        },
                        icon: const Icon(Icons.flag),
                        label: const Text('Proceed to End Ride & Metering'),
                        style: FilledButton.styleFrom(
                          minimumSize: const Size.fromHeight(52),
                          backgroundColor: const Color(0xff0f766e),
                          shape: RoundedRectangleBorder(
                            borderRadius: BorderRadius.circular(10),
                          ),
                        ),
                      )
                    : OutlinedButton(
                        onPressed: () => Navigator.of(context).pop(),
                        style: OutlinedButton.styleFrom(
                          minimumSize: const Size.fromHeight(48),
                          shape: RoundedRectangleBorder(
                            borderRadius: BorderRadius.circular(10),
                          ),
                        ),
                        child: const Text('Close'),
                      ),
              ),
            ],
          ),
        );
      },
    );
  }
}

class _StatusBadge extends StatelessWidget {
  const _StatusBadge({required this.status});

  final TripStatus status;

  @override
  Widget build(BuildContext context) {
    final color = switch (status) {
      TripStatus.active => const Color(0xff059669),
      TripStatus.enRoutePickup => const Color(0xffd97706),
      TripStatus.arrivedAtPickup => const Color(0xff2563eb),
      TripStatus.completed => const Color(0xff4b5563),
      _ => const Color(0xff6b7280),
    };

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
      decoration: BoxDecoration(
        color: color.withOpacity(0.12),
        borderRadius: BorderRadius.circular(6),
        border: Border.all(color: color.withOpacity(0.3)),
      ),
      child: Text(
        status.label,
        style: TextStyle(
          fontSize: 12,
          fontWeight: FontWeight.w800,
          color: color,
        ),
      ),
    );
  }
}

class _LocationRow extends StatelessWidget {
  const _LocationRow({
    required this.icon,
    required this.iconColor,
    required this.title,
    required this.city,
    required this.address,
    this.time,
  });

  final IconData icon;
  final Color iconColor;
  final String title;
  final String city;
  final String address;
  final String? time;

  @override
  Widget build(BuildContext context) {
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Icon(icon, color: iconColor, size: 22),
        const SizedBox(width: 12),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Text(
                    title,
                    style: const TextStyle(
                      fontSize: 12,
                      fontWeight: FontWeight.bold,
                      color: Color(0xff6b7280),
                    ),
                  ),
                  if (time != null)
                    Text(
                      time!,
                      style: const TextStyle(
                        fontSize: 12,
                        fontWeight: FontWeight.w600,
                        color: Color(0xff4b5563),
                      ),
                    ),
                ],
              ),
              const SizedBox(height: 2),
              Text(
                city,
                style: const TextStyle(
                  fontSize: 16,
                  fontWeight: FontWeight.bold,
                  color: Color(0xff111827),
                ),
              ),
              Text(
                address,
                style: const TextStyle(
                  fontSize: 13,
                  color: Color(0xff4b5563),
                ),
              ),
            ],
          ),
        ),
      ],
    );
  }
}

class _DetailRow extends StatelessWidget {
  const _DetailRow({
    required this.icon,
    required this.label,
    required this.value,
    this.valueColor,
  });

  final IconData icon;
  final String label;
  final String value;
  final Color? valueColor;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 6),
      child: Row(
        children: [
          Icon(icon, size: 18, color: const Color(0xff6b7280)),
          const SizedBox(width: 10),
          Expanded(
            child: Text(
              label,
              style: const TextStyle(
                fontSize: 13,
                color: Color(0xff4b5563),
              ),
            ),
          ),
          Text(
            value,
            style: TextStyle(
              fontSize: 13,
              fontWeight: FontWeight.bold,
              color: valueColor ?? const Color(0xff111827),
            ),
          ),
        ],
      ),
    );
  }
}
