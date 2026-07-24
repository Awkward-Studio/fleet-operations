class Trip {
  const Trip({
    required this.id,
    required this.customerName,
    required this.customerPhone,
    required this.pickupCity,
    required this.dropCity,
    required this.pickupAddress,
    required this.dropAddress,
    required this.pickupLatitude,
    required this.pickupLongitude,
    required this.pickupAt,
    required this.estimatedDropAt,
    required this.status,
    required this.driver,
    required this.vehicleLabel,
    required this.vehicleOdometerKm,
    required this.notes,
  });

  factory Trip.fromJson(Map<String, dynamic> json) {
    final vehicle = json['vehicle'] as Map<String, dynamic>?;
    final driverJson = json['driver'] as Map<String, dynamic>?;
    final vehicleLabel = vehicle == null
        ? null
        : '${vehicle['registration_number']} - ${vehicle['make']} ${vehicle['model']}';

    return Trip(
      id: json['id'] as int? ?? 0,
      customerName: json['customer_name'] as String? ?? 'Guest',
      customerPhone: json['customer_phone'] as String? ?? '',
      pickupCity: json['pickup_city'] as String? ?? 'Pickup',
      dropCity: json['drop_city'] as String? ?? 'Drop',
      pickupAddress: json['pickup_address'] as String? ?? '',
      dropAddress: json['drop_address'] as String? ?? '',
      pickupLatitude: _parseDouble(json['pickup_latitude']),
      pickupLongitude: _parseDouble(json['pickup_longitude']),
      pickupAt: DateTime.tryParse(json['pickup_at'] as String? ?? ''),
      estimatedDropAt: DateTime.tryParse(
        json['estimated_drop_at'] as String? ?? '',
      ),
      status: TripStatusX.fromValue(json['status'] as String? ?? 'requested'),
      driver: driverJson == null ? null : Driver.fromJson(driverJson),
      vehicleLabel: vehicleLabel,
      vehicleOdometerKm: vehicle == null
          ? 0
          : int.tryParse('${vehicle['odometer_km'] ?? 0}') ?? 0,
      notes: json['notes'] as String?,
    );
  }

  final int id;
  final String customerName;
  final String customerPhone;
  final String pickupCity;
  final String dropCity;
  final String pickupAddress;
  final String dropAddress;
  final double? pickupLatitude;
  final double? pickupLongitude;
  final DateTime? pickupAt;
  final DateTime? estimatedDropAt;
  final TripStatus status;
  final Driver? driver;
  final String? vehicleLabel;
  final int vehicleOdometerKm;
  final String? notes;

  String get pickupAddressLabel =>
      pickupAddress.trim().isEmpty ? pickupCity : pickupAddress;

  String get dropAddressLabel =>
      dropAddress.trim().isEmpty ? dropCity : dropAddress;

  bool get hasAction => status.nextActionLabel != null;

  bool get hasPickupCoordinates =>
      pickupLatitude != null && pickupLongitude != null;

  String get pickupNavigationLabel {
    if (pickupAddress.trim().isNotEmpty) return pickupAddress;
    return pickupCity;
  }

  static double? _parseDouble(dynamic value) {
    if (value == null || value == '') return null;
    if (value is num) return value.toDouble();
    return double.tryParse(value.toString());
  }
}

class Driver {
  const Driver({
    required this.id,
    required this.name,
    required this.phone,
    required this.status,
  });

  factory Driver.fromJson(Map<String, dynamic> json) {
    return Driver(
      id: json['id'] as int? ?? 0,
      name: json['name'] as String? ?? 'Driver',
      phone: json['phone'] as String? ?? '',
      status: json['status'] as String? ?? 'available',
    );
  }

  final int id;
  final String name;
  final String phone;
  final String status;
}

enum TripStatus {
  requested,
  assigned,
  enRoutePickup,
  arrivedAtPickup,
  active,
  completed,
  cancelled,
}

extension TripStatusX on TripStatus {
  static TripStatus fromValue(String value) {
    return switch (value) {
      'assigned' => TripStatus.assigned,
      'en_route_pickup' => TripStatus.enRoutePickup,
      'arrived_at_pickup' => TripStatus.arrivedAtPickup,
      'active' => TripStatus.active,
      'completed' => TripStatus.completed,
      'cancelled' => TripStatus.cancelled,
      _ => TripStatus.requested,
    };
  }

  String get value {
    return switch (this) {
      TripStatus.requested => 'requested',
      TripStatus.assigned => 'assigned',
      TripStatus.enRoutePickup => 'en_route_pickup',
      TripStatus.arrivedAtPickup => 'arrived_at_pickup',
      TripStatus.active => 'active',
      TripStatus.completed => 'completed',
      TripStatus.cancelled => 'cancelled',
    };
  }

  String get label {
    return switch (this) {
      TripStatus.assigned => 'ASSIGNED',
      TripStatus.enRoutePickup => 'EN ROUTE',
      TripStatus.arrivedAtPickup => 'AT PICKUP',
      TripStatus.active => 'ACTIVE',
      TripStatus.completed => 'COMPLETED',
      TripStatus.cancelled => 'CANCELLED',
      TripStatus.requested => 'REQUESTED',
    };
  }

  String? get nextActionLabel {
    return switch (this) {
      TripStatus.assigned => 'Start Pre-Ride Inspection',
      TripStatus.enRoutePickup => 'Navigate / Arrived at Pickup',
      TripStatus.arrivedAtPickup => 'Verify Guest OTP',
      TripStatus.active => 'View Active Trip & Telemetry',
      _ => null,
    };
  }
}
