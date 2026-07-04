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

## Startup probe timeout classification

`tools/pi5_validate_uat_decoder_tooling.sh` starts `runtime/bin/dump978-fa`
under `timeout` for a short non-persistent SDR-open probe. Exit code 124 from
`timeout` is expected when `dump978-fa` successfully opens the UAT receiver and
keeps running until the validator stops it.

The validator should fail only on known fatal startup/configuration patterns
such as missing devices, permission problems, busy receivers, or failed SDR-open
messages. Generic log words such as `error` are not sufficient by themselves,
because long-running SDR programs can print normal shutdown/error-handler text
when `timeout` sends SIGTERM.
## Startup timeout classifier

The UAT decoder tooling validator intentionally runs `dump978-fa` under a short timeout.  Exit code `124` from GNU `timeout` is treated as success when no strong pre-timeout startup/configuration errors are present, because a persistent decoder should continue running until stopped.


## Validator classifier note

For the non-persistent `dump978-fa` startup probe, `timeout` exit code 124 is a pass condition. It means the decoder stayed alive until the validator deliberately stopped it. The validator must classify 124 before broad shutdown-log scanning, because a controlled stop can emit generic text that is not a startup or SDR-open failure.
