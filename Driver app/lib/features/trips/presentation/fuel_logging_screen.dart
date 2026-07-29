import 'dart:io';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:geolocator/geolocator.dart';
import 'package:image_picker/image_picker.dart';

import '../../../core/providers.dart';
import '../data/trip_providers.dart';
import '../domain/trip.dart';

class FuelLoggingScreen extends ConsumerStatefulWidget {
  const FuelLoggingScreen({super.key});

  @override
  ConsumerState<FuelLoggingScreen> createState() => _FuelLoggingScreenState();
}

class _FuelLoggingScreenState extends ConsumerState<FuelLoggingScreen> {
  final _formKey = GlobalKey<FormState>();
  final _odometerController = TextEditingController();
  final _quantityController = TextEditingController();
  final _amountController = TextEditingController();
  final _priceController = TextEditingController();
  final _vendorController = TextEditingController();
  final _notesController = TextEditingController();

  final List<File> _selectedImages = [];
  final ImagePicker _picker = ImagePicker();

  double? _latitude;
  double? _longitude;
  bool _locating = false;
  String _locationStatus = 'Determining location...';
  bool _submitting = false;

  @override
  void initState() {
    super.initState();
    _initLocation();
  }

  @override
  void dispose() {
    _odometerController.dispose();
    _quantityController.dispose();
    _amountController.dispose();
    _priceController.dispose();
    _vendorController.dispose();
    _notesController.dispose();
    super.dispose();
  }

  Future<Position?> _getCurrentLocation() async {
    bool serviceEnabled;
    LocationPermission permission;

    serviceEnabled = await Geolocator.isLocationServiceEnabled();
    if (!serviceEnabled) return null;

    permission = await Geolocator.checkPermission();
    if (permission == LocationPermission.denied) {
      permission = await Geolocator.requestPermission();
      if (permission == LocationPermission.denied) return null;
    }

    if (permission == LocationPermission.deniedForever) return null;

    return await Geolocator.getCurrentPosition(
      desiredAccuracy: LocationAccuracy.high,
      timeLimit: const Duration(seconds: 8),
    );
  }

  Future<void> _initLocation() async {
    if (!mounted) return;
    setState(() {
      _locating = true;
      _locationStatus = 'Determining location...';
    });

    try {
      final pos = await _getCurrentLocation();
      if (!mounted) return;
      if (pos != null) {
        setState(() {
          _latitude = pos.latitude;
          _longitude = pos.longitude;
          _locationStatus = 'Current Location Captured ✓';
        });
      } else {
        setState(() {
          _locationStatus = 'Location Services Unavailable ⚠';
        });
      }
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _locationStatus = 'Location Capture Failed ⚠';
      });
    } finally {
      if (mounted) {
        setState(() {
          _locating = false;
        });
      }
    }
  }

  Future<void> _pickImage(ImageSource source) async {
    try {
      // Compress automatically via setting quality and size limits
      final pickedFile = await _picker.pickImage(
        source: source,
        imageQuality: 70,
        maxWidth: 1200,
      );

      if (pickedFile != null && mounted) {
        setState(() {
          _selectedImages.add(File(pickedFile.path));
        });
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(
          context,
        ).showSnackBar(SnackBar(content: Text('Failed to pick image: $e')));
      }
    }
  }

  void _showImagePickerOptions() {
    showModalBottomSheet(
      context: context,
      builder: (context) => SafeArea(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            ListTile(
              leading: const Icon(Icons.camera_alt, color: Color(0xff0f766e)),
              title: const Text('Capture with Camera'),
              onTap: () {
                Navigator.of(context).pop();
                _pickImage(ImageSource.camera);
              },
            ),
            ListTile(
              leading: const Icon(
                Icons.photo_library,
                color: Color(0xff0f766e),
              ),
              title: const Text('Choose from Gallery'),
              onTap: () {
                Navigator.of(context).pop();
                _pickImage(ImageSource.gallery);
              },
            ),
          ],
        ),
      ),
    );
  }

  Future<void> _submit() async {
    if (!_formKey.currentState!.validate()) return;

    final tripState = ref.read(currentDriverTripProvider);
    final driverState = ref.read(driverProfileProvider);

    final currentTrip = tripState.asData?.value;
    final driverInfo = driverState.asData?.value;

    int? vehicleId;
    int? driverId;
    int? currentOdometer;

    if (currentTrip != null) {
      vehicleId = currentTrip.vehicleOdometerKm > 0
          ? currentTrip.id
          : null; // placeholder for checking vehicle
      // Let's resolve vehicle id from active trip details
      // Actually, active trip has vehicle label, but wait, does it have vehicle id?
      // Trip domain in Flutter app:
      // final int id; final String customerName; ... final Driver? driver; final String? vehicleLabel; final int vehicleOdometerKm;
      // Wait, let's verify if Trip has vehicle id or vehicle object. In JSON, trip has a vehicle map. Let's inspect trip.dart line 26:
      // final vehicle = json['vehicle'] as Map<String, dynamic>?;
      // Ah! Trip.fromJson parses vehicleLabel and vehicleOdometerKm, but it does NOT store vehicle object directly in Trip.
      // Wait, but `/fleet/driver/my-trips/current/` returns the full TripSerializer data, which contains `vehicle_id` and `vehicle`!
      // In trip.dart, Trip.fromJson extracts `vehicle` as Map:
      // final vehicle = json['vehicle'] as Map<String, dynamic>?;
      // We can easily extract vehicle['id'] or driver['id'] if they are present!
      // Let's look at tripState.valueOrNull. Yes, `currentTrip.driver?.id` is the driver ID. What about the vehicle ID?
      // In trip.dart, Trip.fromJson does not save vehicle ID, but we can look at the raw json response!
      // Wait! Or we can get it from the driverProfileProvider!
      // `driverProfileProvider` fetches `/api/fleet/drivers/me/` which returns `DriverSerializer` data, which includes:
      // "id", "current_vehicle" (which is a map: {id, registration_number, make, model, odometer_km})
      // So if driver profile is loaded, we can read vehicle ID from `driverInfo['current_vehicle']['id']`!
      // What about driver ID? `driverInfo['id']`!
      // This is extremely reliable!
    }

    if (driverInfo != null) {
      driverId = driverInfo['id'] as int?;
      final vehicleMap = driverInfo['current_vehicle'] as Map<String, dynamic>?;
      if (vehicleMap != null) {
        vehicleId = vehicleMap['id'] as int?;
        currentOdometer = vehicleMap['odometer_km'] as int?;
      }
    }

    if (vehicleId == null || driverId == null) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text(
            'Cannot resolve your assigned vehicle. Please make sure dispatch has assigned a vehicle to your profile.',
          ),
          backgroundColor: Colors.red,
        ),
      );
      return;
    }

    final enteredOdometer = int.tryParse(_odometerController.text) ?? 0;
    if (currentOdometer != null && enteredOdometer < currentOdometer) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(
            'Odometer reading ($enteredOdometer) cannot be less than the current odometer of the vehicle ($currentOdometer km).',
          ),
          backgroundColor: Colors.red,
        ),
      );
      return;
    }

    setState(() => _submitting = true);

    try {
      final api = ref.read(apiClientProvider);

      // Auto-compute price per litre if not entered
      double quantity = double.tryParse(_quantityController.text) ?? 0.0;
      double totalAmount = double.tryParse(_amountController.text) ?? 0.0;
      double unitPrice = double.tryParse(_priceController.text) ?? 0.0;

      if (unitPrice == 0.0 && quantity > 0) {
        unitPrice = totalAmount / quantity;
      }

      final fields = {
        'vehicle': vehicleId.toString(),
        'driver': driverId.toString(),
        if (currentTrip != null) 'trip': currentTrip.id.toString(),
        'odometer_km': enteredOdometer.toString(),
        'quantity': quantity.toStringAsFixed(2),
        'unit_price': unitPrice.toStringAsFixed(2),
        'total_amount': totalAmount.toStringAsFixed(2),
        'vendor': _vendorController.text.trim(),
        'notes': _notesController.text.trim(),
        'source': 'mobile_app',
        'transaction_datetime': DateTime.now().toUtc().toIso8601String(),
        if (_latitude != null) 'latitude': _latitude!.toStringAsFixed(8),
        if (_longitude != null) 'longitude': _longitude!.toStringAsFixed(8),
      };

      await api.postMultipartFiles(
        '/fleet/fuel-transactions/',
        fields: fields,
        files: _selectedImages,
        fileField: 'images',
      );

      if (!mounted) return;

      showDialog(
        context: context,
        barrierDismissible: false,
        builder: (context) => AlertDialog(
          icon: const Icon(
            Icons.check_circle_outline,
            color: Color(0xff0f766e),
            size: 48,
          ),
          title: const Text('Log Submitted'),
          content: const Text(
            'Your fuel log has been submitted successfully and is pending fleet manager review.',
          ),
          actions: [
            TextButton(
              onPressed: () {
                Navigator.of(context).pop();
                _clearForm();
              },
              child: const Text(
                'OK',
                style: TextStyle(color: Color(0xff0f766e)),
              ),
            ),
          ],
        ),
      );

      // Refresh driver/trip to update odometer readings in app
      ref.invalidate(driverProfileProvider);
      ref.invalidate(currentDriverTripProvider);
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(
            'Submission failed: ${e.toString().replaceFirst('Exception: ', '')}',
          ),
          backgroundColor: Colors.red,
        ),
      );
    } finally {
      if (mounted) setState(() => _submitting = false);
    }
  }

  void _clearForm() {
    setState(() {
      _odometerController.clear();
      _quantityController.clear();
      _amountController.clear();
      _priceController.clear();
      _vendorController.clear();
      _notesController.clear();
      _selectedImages.clear();
      _initLocation();
    });
  }

  @override
  Widget build(BuildContext context) {
    final tripState = ref.watch(currentDriverTripProvider);
    final driverState = ref.watch(driverProfileProvider);

    return tripState.when(
      loading: () => const Center(child: CircularProgressIndicator()),
      error: (e, _) => Center(child: Text('Error loading assignment: $e')),
      data: (trip) {
        return driverState.when(
          loading: () => const Center(child: CircularProgressIndicator()),
          error: (e, _) =>
              Center(child: Text('Error loading driver profile: $e')),
          data: (driverInfo) {
            final hasActiveTrip =
                trip != null && trip.status == TripStatus.active;

            // Extract assigned vehicle details
            String vehicleReg = '--';
            String vehicleModel = '--';
            int? currentOdo;

            if (driverInfo != null && driverInfo['current_vehicle'] != null) {
              final v = driverInfo['current_vehicle'] as Map<String, dynamic>;
              vehicleReg = v['registration_number'] ?? '--';
              vehicleModel = '${v['make'] ?? ''} ${v['model'] ?? ''}'.trim();
              currentOdo = v['odometer_km'] as int?;
            }

            return Form(
              key: _formKey,
              child: ListView(
                padding: const EdgeInsets.all(16),
                children: [
                  // Vehicle Info Card
                  Card(
                    color: Colors.white,
                    elevation: 0,
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(8),
                      side: const BorderSide(color: Color(0xffdde6e2)),
                    ),
                    child: Padding(
                      padding: const EdgeInsets.all(16),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          const Text(
                            'Vehicle Information',
                            style: TextStyle(
                              fontSize: 16,
                              fontWeight: FontWeight.w800,
                              color: Color(0xff082f2d),
                            ),
                          ),
                          const SizedBox(height: 12),
                          _infoRow('Assigned Vehicle', vehicleModel),
                          _infoRow('Vehicle Number', vehicleReg),
                          if (currentOdo != null)
                            _infoRow('Current Odometer', '$currentOdo km'),
                          _infoRow(
                            'Current Trip',
                            hasActiveTrip
                                ? 'Trip #${trip.id} (Active)'
                                : 'None',
                            valColor: hasActiveTrip
                                ? const Color(0xff0f766e)
                                : Colors.black54,
                          ),
                        ],
                      ),
                    ),
                  ),
                  const SizedBox(height: 16),

                  // Fuel Details Card
                  Card(
                    color: Colors.white,
                    elevation: 0,
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(8),
                      side: const BorderSide(color: Color(0xffdde6e2)),
                    ),
                    child: Padding(
                      padding: const EdgeInsets.all(16),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          const Text(
                            'Fuel Details',
                            style: TextStyle(
                              fontSize: 16,
                              fontWeight: FontWeight.w800,
                              color: Color(0xff082f2d),
                            ),
                          ),
                          const SizedBox(height: 16),

                          // Odometer Input
                          TextFormField(
                            controller: _odometerController,
                            keyboardType: TextInputType.number,
                            decoration: InputDecoration(
                              labelText: 'Odometer Reading (km) *',
                              hintText: currentOdo != null
                                  ? 'Must be ≥ $currentOdo'
                                  : 'e.g. 10450',
                              prefixIcon: const Icon(Icons.speed),
                            ),
                            validator: (val) {
                              if (val == null || val.isEmpty) {
                                return 'Please enter odometer reading';
                              }
                              final numVal = int.tryParse(val);
                              if (numVal == null || numVal <= 0) {
                                return 'Enter a valid odometer reading';
                              }
                              return null;
                            },
                          ),
                          const SizedBox(height: 14),

                          // Quantity & Amount Row
                          Row(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Expanded(
                                child: TextFormField(
                                  controller: _quantityController,
                                  keyboardType:
                                      const TextInputType.numberWithOptions(
                                        decimal: true,
                                      ),
                                  decoration: const InputDecoration(
                                    labelText: 'Quantity (Litres) *',
                                    hintText: 'e.g. 24.5',
                                    prefixIcon: Icon(Icons.water_drop_outlined),
                                  ),
                                  validator: (val) {
                                    if (val == null || val.isEmpty) {
                                      return 'Required';
                                    }
                                    final numVal = double.tryParse(val);
                                    if (numVal == null || numVal <= 0) {
                                      return 'Invalid';
                                    }
                                    return null;
                                  },
                                ),
                              ),
                              const SizedBox(width: 12),
                              Expanded(
                                child: TextFormField(
                                  controller: _amountController,
                                  keyboardType:
                                      const TextInputType.numberWithOptions(
                                        decimal: true,
                                      ),
                                  decoration: const InputDecoration(
                                    labelText: 'Total Paid (₹) *',
                                    hintText: 'e.g. 2500',
                                    prefixIcon: Icon(Icons.currency_rupee),
                                  ),
                                  validator: (val) {
                                    if (val == null || val.isEmpty) {
                                      return 'Required';
                                    }
                                    final numVal = double.tryParse(val);
                                    if (numVal == null || numVal <= 0) {
                                      return 'Invalid';
                                    }
                                    return null;
                                  },
                                ),
                              ),
                            ],
                          ),
                          const SizedBox(height: 14),

                          // Price Per Litre (Optional)
                          TextFormField(
                            controller: _priceController,
                            keyboardType: const TextInputType.numberWithOptions(
                              decimal: true,
                            ),
                            decoration: const InputDecoration(
                              labelText: 'Price Per Litre (Optional)',
                              hintText: 'Leave empty to auto-calculate',
                              prefixIcon: Icon(
                                Icons.local_gas_station_outlined,
                              ),
                            ),
                          ),
                          const SizedBox(height: 14),

                          // Vendor Name
                          TextFormField(
                            controller: _vendorController,
                            textCapitalization: TextCapitalization.words,
                            decoration: const InputDecoration(
                              labelText: 'Petrol Pump / Vendor Name *',
                              hintText: 'e.g. Shell Petrol Pump',
                              prefixIcon: Icon(Icons.storefront),
                            ),
                            validator: (val) {
                              if (val == null || val.trim().isEmpty) {
                                return 'Please enter vendor name';
                              }
                              return null;
                            },
                          ),
                          const SizedBox(height: 14),

                          // Notes
                          TextFormField(
                            controller: _notesController,
                            textCapitalization: TextCapitalization.sentences,
                            maxLines: 2,
                            decoration: const InputDecoration(
                              labelText: 'Notes (Optional)',
                              hintText: 'e.g. Card payment, tank full fill',
                              prefixIcon: Icon(Icons.note_alt_outlined),
                            ),
                          ),
                        ],
                      ),
                    ),
                  ),
                  const SizedBox(height: 16),

                  // Receipt Photos Card
                  Card(
                    color: Colors.white,
                    elevation: 0,
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(8),
                      side: const BorderSide(color: Color(0xffdde6e2)),
                    ),
                    child: Padding(
                      padding: const EdgeInsets.all(16),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Row(
                            mainAxisAlignment: MainAxisAlignment.spaceBetween,
                            children: [
                              const Text(
                                'Receipt / Pump Photos',
                                style: TextStyle(
                                  fontSize: 16,
                                  fontWeight: FontWeight.w800,
                                  color: Color(0xff082f2d),
                                ),
                              ),
                              IconButton(
                                icon: const Icon(
                                  Icons.add_a_photo,
                                  color: Color(0xff0f766e),
                                ),
                                onPressed: _showImagePickerOptions,
                                tooltip: 'Add image',
                              ),
                            ],
                          ),
                          const SizedBox(height: 8),
                          if (_selectedImages.isEmpty)
                            const Padding(
                              padding: EdgeInsets.symmetric(vertical: 16),
                              child: Center(
                                child: Text(
                                  'No photos attached.\nPlease capture a photo of the receipt or pump display.',
                                  textAlign: TextAlign.center,
                                  style: TextStyle(
                                    color: Colors.black45,
                                    fontSize: 13,
                                  ),
                                ),
                              ),
                            )
                          else
                            GridView.builder(
                              shrinkWrap: true,
                              physics: const NeverScrollableScrollPhysics(),
                              gridDelegate:
                                  const SliverGridDelegateWithFixedCrossAxisCount(
                                    crossAxisCount: 3,
                                    crossAxisSpacing: 8,
                                    mainAxisSpacing: 8,
                                  ),
                              itemCount: _selectedImages.length,
                              itemBuilder: (context, index) {
                                final file = _selectedImages[index];
                                return Stack(
                                  fit: StackFit.expand,
                                  children: [
                                    ClipRRect(
                                      borderRadius: BorderRadius.circular(6),
                                      child: Image.file(
                                        file,
                                        fit: BoxFit.cover,
                                      ),
                                    ),
                                    Positioned(
                                      top: 4,
                                      right: 4,
                                      child: GestureDetector(
                                        onTap: () {
                                          setState(() {
                                            _selectedImages.removeAt(index);
                                          });
                                        },
                                        child: CircleAvatar(
                                          radius: 12,
                                          backgroundColor: Colors.black
                                              .withOpacity(0.6),
                                          child: const Icon(
                                            Icons.close,
                                            size: 14,
                                            color: Colors.white,
                                          ),
                                        ),
                                      ),
                                    ),
                                  ],
                                );
                              },
                            ),
                        ],
                      ),
                    ),
                  ),
                  const SizedBox(height: 16),

                  // Location Display Card
                  Card(
                    color: Colors.white,
                    elevation: 0,
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(8),
                      side: const BorderSide(color: Color(0xffdde6e2)),
                    ),
                    child: Padding(
                      padding: const EdgeInsets.symmetric(
                        horizontal: 16,
                        vertical: 12,
                      ),
                      child: Row(
                        children: [
                          Icon(
                            Icons.location_on,
                            color: _latitude != null
                                ? Colors.green
                                : const Color(0xff0f766e),
                          ),
                          const SizedBox(width: 12),
                          Expanded(
                            child: Text(
                              _locationStatus,
                              style: TextStyle(
                                fontWeight: FontWeight.w600,
                                color: _latitude != null
                                    ? Colors.green.shade800
                                    : Colors.black87,
                              ),
                            ),
                          ),
                          if (_locating)
                            const SizedBox(
                              width: 18,
                              height: 18,
                              child: CircularProgressIndicator(strokeWidth: 2),
                            )
                          else
                            IconButton(
                              icon: const Icon(Icons.refresh, size: 18),
                              onPressed: _initLocation,
                              tooltip: 'Refresh location',
                            ),
                        ],
                      ),
                    ),
                  ),
                  const SizedBox(height: 24),

                  // Submit button
                  FilledButton.icon(
                    onPressed: _submitting ? null : _submit,
                    icon: _submitting
                        ? const SizedBox(
                            width: 18,
                            height: 18,
                            child: CircularProgressIndicator(
                              strokeWidth: 2,
                              color: Colors.white,
                            ),
                          )
                        : const Icon(Icons.local_gas_station),
                    label: const Text('Submit Fuel Log'),
                    style: FilledButton.styleFrom(
                      minimumSize: const Size.fromHeight(54),
                      backgroundColor: const Color(0xff0f766e),
                      shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(8),
                      ),
                    ),
                  ),
                  const SizedBox(height: 20),
                ],
              ),
            );
          },
        );
      },
    );
  }

  Widget _infoRow(String label, String value, {Color? valColor}) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4),
      child: Row(
        children: [
          Expanded(
            flex: 2,
            child: Text(
              label,
              style: const TextStyle(
                color: Colors.black54,
                fontWeight: FontWeight.w500,
              ),
            ),
          ),
          Expanded(
            flex: 3,
            child: Text(
              value,
              style: TextStyle(
                fontWeight: FontWeight.w700,
                color: valColor ?? const Color(0xff082f2d),
              ),
            ),
          ),
        ],
      ),
    );
  }
}
