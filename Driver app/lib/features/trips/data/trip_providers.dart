import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/providers.dart';
import '../domain/trip.dart';

final currentDriverTripProvider = FutureProvider<Trip?>((ref) async {
  final api = ref.watch(apiClientProvider);
  final response = await api.get('/fleet/driver/my-trips/current/');
  if (response == null) return null;
  return Trip.fromJson(response as Map<String, dynamic>);
});

final tripActionControllerProvider = Provider<TripActionController>(
  (ref) => TripActionController(ref),
);

class TripActionController {
  const TripActionController(this.ref);

  final Ref ref;

  Future<void> advance(Trip trip) async {
    final api = ref.read(apiClientProvider);
    final nextStatus = switch (trip.status) {
      TripStatus.assigned => TripStatus.enRoutePickup,
      TripStatus.enRoutePickup => TripStatus.arrivedAtPickup,
      TripStatus.arrivedAtPickup => TripStatus.active,
      _ => null,
    };

    if (nextStatus == null) return;
    await api.post('/trips/${trip.id}/transition/', {
      'status': nextStatus.value,
    });
    ref.invalidate(currentDriverTripProvider);
  }
}
