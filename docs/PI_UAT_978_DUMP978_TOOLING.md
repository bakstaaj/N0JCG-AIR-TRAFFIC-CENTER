# V0.2 UAT 978 MHz dump978-fa Tooling

This checkpoint adds app-owned UAT decoder tooling while keeping the persistent UAT runtime disabled until the backend/API integration milestone.

## Decoder choice

The selected decoder is FlightAware `dump978-fa` from `https://github.com/flightaware/dump978`.

Reasons for this choice:

- It is purpose-built for 978 MHz UAT demodulation/decoding.
- It can select an RTL-SDR through SoapySDR using a stable RTL EEPROM serial.
- It can emit decoded JSON to stdout or a TCP JSON port.
- It also builds `skyaware978`, which can later generate SkyAware-compatible JSON files.

## App-owned installation

Run this on the Pi:

```bash
cd ~/sdrdev/PI-AIR-TRAFFIC-TRACKER
./tools/pi5_install_app_owned_dump978.sh
```

The installer downloads/builds upstream source into `runtime/build/dump978-fa-src` and installs the app-owned binaries into:

- `runtime/bin/dump978-fa`
- `runtime/bin/skyaware978`

The script installs required Debian build packages unless `PI_AIR_TRAFFIC_SKIP_APT=1` is set.

## Validation

After installation, run:

```bash
./tools/pi5_validate_uat_decoder_tooling.sh
```

The validator checks:

- app-owned binaries exist and are executable;
- `dump978-fa --help` exposes expected UAT/Soapy options;
- the UAT serial resolves to one RTL receiver;
- SoapySDR can see the UAT receiver by serial;
- a short `dump978-fa` SDR startup probe can open serial `00000978` without starting a persistent service.

## Runtime state

This milestone does not start or enable a persistent UAT decoder service. The `/api/status` role contract should continue reporting UAT serial `00000978` as disabled until the backend service integration milestone.
