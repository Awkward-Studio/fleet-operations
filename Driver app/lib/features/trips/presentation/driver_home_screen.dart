import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:url_launcher/url_launcher.dart';

import '../../../core/api_client.dart';
import '../data/trip_providers.dart';
import '../domain/trip.dart';
import 'pre_ride_inspection_screen.dart';
import 'pickup_navigation_screen.dart';

class DriverHomeScreen extends ConsumerWidget {
  const DriverHomeScreen({super.key, required this.onLogout});

  final VoidCallback onLogout;

  Future<void> _logout() async {
    await TokenStore.clear();
    onLogout();
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final tripState = ref.watch(currentDriverTripProvider);

    return Scaffold(
      appBar: AppBar(
        title: const Text('Driver Dashboard'),
        actions: [
          IconButton(
            tooltip: 'Refresh',
            onPressed: () => ref.invalidate(currentDriverTripProvider),
            icon: const Icon(Icons.refresh),
          ),
          IconButton(
            tooltip: 'Sign out',
            onPressed: _logout,
            icon: const Icon(Icons.logout),
          ),
        ],
      ),
      body: tripState.when(
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (error, _) => _DashboardError(
          message: error.toString().replaceFirst('Exception: ', ''),
          onRetry: () => ref.invalidate(currentDriverTripProvider),
        ),
        data: (trip) => RefreshIndicator(
          onRefresh: () => ref.refresh(currentDriverTripProvider.future),
          child: ListView(
            physics: const AlwaysScrollableScrollPhysics(),
            padding: const EdgeInsets.fromLTRB(16, 10, 16, 24),
            children: [
              _Header(trip: trip),
              const SizedBox(height: 18),
              if (trip == null)
                const _EmptyTripState()
              else
                ActiveTripCard(trip: trip),
            ],
          ),
        ),
      ),
    );
  }
}

class _Header extends StatelessWidget {
  const _Header({required this.trip});

  final Trip? trip;

  @override
  Widget build(BuildContext context) {
    final driver = trip?.driver;
    final driverName = driver?.name ?? 'Driver';
    final shiftStatus = _shiftStatus(driver?.status, trip?.status);

    return Row(
      children: [
        CircleAvatar(
          radius: 26,
          backgroundColor: const Color(0xff082f2d),
          child: Text(
            driverName.characters.first.toUpperCase(),
            style: const TextStyle(
              color: Colors.white,
              fontWeight: FontWeight.w900,
              fontSize: 20,
            ),
          ),
        ),
        const SizedBox(width: 12),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                'Hi, $driverName',
                style: const TextStyle(
                  color: Color(0xff082f2d),
                  fontSize: 26,
                  fontWeight: FontWeight.w900,
                ),
              ),
              const Text(
                "Today's assignment",
                style: TextStyle(color: Color(0xff64736f)),
              ),
            ],
          ),
        ),
        _ShiftStatusPill(label: shiftStatus),
      ],
    );
  }

  String _shiftStatus(String? driverStatus, TripStatus? tripStatus) {
    if (tripStatus == TripStatus.active) return 'On Trip';
    if (tripStatus == TripStatus.assigned ||
        tripStatus == TripStatus.enRoutePickup ||
        tripStatus == TripStatus.arrivedAtPickup) {
      return 'Assigned';
    }
    if (driverStatus == 'on_trip') return 'On Trip';
    if (driverStatus == 'assigned') return 'Assigned';
    return 'Available';
  }
}

class ActiveTripCard extends ConsumerWidget {
  const ActiveTripCard({super.key, required this.trip});

  final Trip trip;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return Container(
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: const Color(0xffdde6e2)),
        boxShadow: const [
          BoxShadow(
            color: Color(0x12000000),
            blurRadius: 18,
            offset: Offset(0, 10),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 16, 16, 12),
            child: Row(
              children: [
                const Expanded(
                  child: Text(
                    'Active Trip',
                    style: TextStyle(fontSize: 20, fontWeight: FontWeight.w900),
                  ),
                ),
                _TripStatusPill(status: trip.status),
              ],
            ),
          ),
          const Divider(height: 1),
          Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                _RouteOverview(trip: trip),
                const SizedBox(height: 16),
                _AddressBlock(
                  icon: Icons.radio_button_checked,
                  title: 'Pickup',
                  city: trip.pickupCity,
                  address: trip.pickupAddressLabel,
                  time: _formatTime(trip.pickupAt),
                ),
                const SizedBox(height: 12),
                _AddressBlock(
                  icon: Icons.flag,
                  title: 'Dropoff',
                  city: trip.dropCity,
                  address: trip.dropAddressLabel,
                  time: _formatTime(trip.estimatedDropAt),
                ),
                const SizedBox(height: 16),
                _GuestInfo(trip: trip),
                if (trip.vehicleLabel != null) ...[
                  const SizedBox(height: 12),
                  _InfoStrip(
                    icon: Icons.directions_car,
                    text: trip.vehicleLabel!,
                  ),
                ],
                const SizedBox(height: 18),
                FilledButton.icon(
                  onPressed: trip.hasAction
                      ? () async {
                          if (trip.status == TripStatus.assigned) {
                            final submitted = await Navigator.of(context)
                                .push<bool>(
                                  MaterialPageRoute(
                                    builder: (_) =>
                                        PreRideInspectionScreen(trip: trip),
                                  ),
                                );
                            if (submitted == true) {
                              final nextTrip = await ref.refresh(
                                currentDriverTripProvider.future,
                              );
                              if (context.mounted &&
                                  nextTrip?.status ==
                                      TripStatus.enRoutePickup) {
                                await Navigator.of(context).push<bool>(
                                  MaterialPageRoute(
                                    builder: (_) =>
                                        PickupNavigationScreen(trip: nextTrip!),
                                  ),
                                );
                                ref.invalidate(currentDriverTripProvider);
                              }
                            }
                            return;
                          }
                          if (trip.status == TripStatus.enRoutePickup) {
                            final changed = await Navigator.of(context)
                                .push<bool>(
                                  MaterialPageRoute(
                                    builder: (_) =>
                                        PickupNavigationScreen(trip: trip),
                                  ),
                                );
                            if (changed == true) {
                              ref.invalidate(currentDriverTripProvider);
                            }
                            return;
                          }
                          if (trip.status == TripStatus.arrivedAtPickup) {
                            final changed = await showModalBottomSheet<bool>(
                              context: context,
                              isScrollControlled: true,
                              useSafeArea: true,
                              builder: (_) =>
                                  GuestOtpVerificationModal(trip: trip),
                            );
                            if (changed == true) {
                              ref.invalidate(currentDriverTripProvider);
                            }
                            return;
                          }
                          await ref
                              .read(tripActionControllerProvider)
                              .advance(trip);
                        }
                      : null,
                  icon: const Icon(Icons.arrow_forward),
                  label: Text(trip.status.nextActionLabel ?? 'No action'),
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
        ],
      ),
    );
  }
}

class _RouteOverview extends StatelessWidget {
  const _RouteOverview({required this.trip});

  final Trip trip;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: const Color(0xfff6f8f7),
        borderRadius: BorderRadius.circular(8),
      ),
      child: Row(
        children: [
          Expanded(
            child: _RouteCity(label: 'Pickup', city: trip.pickupCity),
          ),
          const Padding(
            padding: EdgeInsets.symmetric(horizontal: 10),
            child: Icon(Icons.arrow_forward, color: Color(0xff0f766e)),
          ),
          Expanded(
            child: _RouteCity(label: 'Drop', city: trip.dropCity),
          ),
        ],
      ),
    );
  }
}

class _RouteCity extends StatelessWidget {
  const _RouteCity({required this.label, required this.city});

  final String label;
  final String city;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          label,
          style: const TextStyle(
            color: Color(0xff64736f),
            fontSize: 12,
            fontWeight: FontWeight.w700,
          ),
        ),
        Text(
          city,
          maxLines: 2,
          overflow: TextOverflow.ellipsis,
          style: const TextStyle(
            color: Color(0xff082f2d),
            fontSize: 18,
            fontWeight: FontWeight.w900,
          ),
        ),
      ],
    );
  }
}

class _AddressBlock extends StatelessWidget {
  const _AddressBlock({
    required this.icon,
    required this.title,
    required this.city,
    required this.address,
    required this.time,
  });

  final IconData icon;
  final String title;
  final String city;
  final String address;
  final String time;

  @override
  Widget build(BuildContext context) {
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Icon(icon, color: const Color(0xff0f766e), size: 22),
        const SizedBox(width: 10),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Expanded(
                    child: Text(
                      '$title - $city',
                      style: const TextStyle(fontWeight: FontWeight.w900),
                    ),
                  ),
                  _TimeBadge(time: time),
                ],
              ),
              const SizedBox(height: 4),
              Text(
                address,
                style: const TextStyle(color: Color(0xff64736f), height: 1.35),
              ),
            ],
          ),
        ),
      ],
    );
  }
}

class _GuestInfo extends StatelessWidget {
  const _GuestInfo({required this.trip});

  final Trip trip;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        border: Border.all(color: const Color(0xffdde6e2)),
        borderRadius: BorderRadius.circular(8),
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
        ],
      ),
    );
  }
}

class _TripStatusPill extends StatelessWidget {
  const _TripStatusPill({required this.status});

  final TripStatus status;

  @override
  Widget build(BuildContext context) {
    final colors = switch (status) {
      TripStatus.assigned => (const Color(0xfffff7ed), const Color(0xffb45309)),
      TripStatus.enRoutePickup => (
        const Color(0xffeff6ff),
        const Color(0xff1d4ed8),
      ),
      TripStatus.arrivedAtPickup => (
        const Color(0xfff5f3ff),
        const Color(0xff6d28d9),
      ),
      TripStatus.active => (const Color(0xffe8f3ef), const Color(0xff0f766e)),
      _ => (const Color(0xfff1f5f9), const Color(0xff475569)),
    };

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
      decoration: BoxDecoration(
        color: colors.$1,
        borderRadius: BorderRadius.circular(999),
      ),
      child: Text(
        status.label,
        style: TextStyle(
          color: colors.$2,
          fontSize: 12,
          fontWeight: FontWeight.w900,
        ),
      ),
    );
  }
}

class _ShiftStatusPill extends StatelessWidget {
  const _ShiftStatusPill({required this.label});

  final String label;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 7),
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
    );
  }
}

class _TimeBadge extends StatelessWidget {
  const _TimeBadge({required this.time});

  final String time;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 5),
      decoration: BoxDecoration(
        color: const Color(0xffe8f3ef),
        borderRadius: BorderRadius.circular(6),
      ),
      child: Text(
        time,
        style: const TextStyle(
          color: Color(0xff0f766e),
          fontSize: 12,
          fontWeight: FontWeight.w800,
        ),
      ),
    );
  }
}

class _InfoStrip extends StatelessWidget {
  const _InfoStrip({required this.icon, required this.text});

  final IconData icon;
  final String text;

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Icon(icon, size: 18, color: const Color(0xff64736f)),
        const SizedBox(width: 8),
        Expanded(
          child: Text(text, style: const TextStyle(color: Color(0xff31413d))),
        ),
      ],
    );
  }
}

class _EmptyTripState extends StatelessWidget {
  const _EmptyTripState();

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: const Color(0xffdde6e2)),
      ),
      child: const Column(
        children: [
          Icon(
            Icons.event_available_outlined,
            size: 42,
            color: Color(0xff0f766e),
          ),
          SizedBox(height: 12),
          Text(
            'No assigned trips',
            style: TextStyle(fontSize: 18, fontWeight: FontWeight.w900),
          ),
          SizedBox(height: 6),
          Text(
            'New assignments will appear here as soon as dispatch assigns one to your profile.',
            textAlign: TextAlign.center,
            style: TextStyle(color: Color(0xff64736f), height: 1.35),
          ),
        ],
      ),
    );
  }
}

class _DashboardError extends StatelessWidget {
  const _DashboardError({required this.message, required this.onRetry});

  final String message;
  final VoidCallback onRetry;

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Icon(
              Icons.cloud_off_outlined,
              size: 44,
              color: Color(0xff9f1d14),
            ),
            const SizedBox(height: 12),
            const Text(
              'Could not load dashboard',
              style: TextStyle(fontWeight: FontWeight.w900),
            ),
            const SizedBox(height: 8),
            Text(
              message,
              textAlign: TextAlign.center,
              style: const TextStyle(color: Color(0xff64736f)),
            ),
            const SizedBox(height: 16),
            OutlinedButton.icon(
              onPressed: onRetry,
              icon: const Icon(Icons.refresh),
              label: const Text('Retry'),
            ),
          ],
        ),
      ),
    );
  }
}

String _formatTime(DateTime? value) {
  if (value == null) return '--:--';
  final local = value.toLocal();
  final hour = local.hour.toString().padLeft(2, '0');
  final minute = local.minute.toString().padLeft(2, '0');
  return '$hour:$minute';
}
