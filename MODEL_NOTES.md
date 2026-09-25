# Model notes and deployment boundary

SwarmShield is an offline decision-support simulation. It does not ingest live sensor data, command aircraft, communicate over radios, or authorize an engagement. Its purpose is to make scarcity, changing information, and coordination failures testable and visible.

## What the model computes

- The synthetic map uses metres in two horizontal dimensions. Protected locations are circular zones with configurable radii and consequence weights. The rendered road grid is illustrative, not GIS data.
- A track has a position, constant velocity until a scripted change, a named protected zone, and a supplied hostility confidence. The simulator solves for the first time its straight-line path enters that zone. A path that misses it is not treated as an impact.
- A track's displayed priority is `confidence × consequence × urgency`. The urgency factor increases as the predicted zone-entry time approaches. These values are scenario scores, not calibrated probabilities of harm or casualty estimates.
- A possible interceptor–track pairing is rejected if the model's rear-pursuit, range, battery, or time-before-impact checks fail. Feasible pairings receive a heuristic utility score. A rectangular assignment solver selects at most one track per available interceptor, including a zero-value **leave unassigned** option.
- SwarmShield revisits uncommitted assignments every five simulated seconds and immediately after a scripted change. The baseline chooses nearest feasible pairings once and holds them. Both strategies receive separate copies of exactly the same scenario.
- The simulation advances at one-second steps. A pairing's heuristic “success probability” affects its score but is **not sampled**; an interception is a deterministic distance test. An interceptor is single-use after an interception.

The generator offers Mixed, Concentrated, Dispersed, and Uncertain scenario patterns. A seed initializes its pseudorandom generator. The same seed and controls reproduce the same scenario; a different seed tests a different case. Custom JSON is available for unusual geometry and event timing. For the largest scenarios, the simulation still runs at one-second resolution but the browser receives fewer visual frames to keep playback usable.

## Changing priorities and coordination

Scripted events can change a track's route and confidence, revise a confidence assessment alone, change a protected zone's consequence, make an interceptor unavailable, degrade peer connectivity, and lose or restore the ground link. Priority and matching are recomputed after these events. The **Live priorities** panel uses the selected strategy's current simulation frame, not just the initial assignment.

Under simulated ground-link loss, interceptors are grouped by a proximity graph. Each connected group considers only tracks inside a configurable visibility radius and makes its own proposal. Disconnected groups do not share a global claim ledger; conflicting claims are exposed in the output and comparison. This is a more honest partition model than assuming perfect shared state, but still **not a peer-to-peer implementation**. The graph is computed centrally by the simulator, and there are no packets, routing, clocks, sensor messages, authentication, or measured radio links.

Mobile ad-hoc networking standards describe neighbour discovery and changing routes, while their security extension addresses message integrity and replay protection: [NHDP](https://www.rfc-editor.org/info/rfc6130/), [OLSRv2](https://www.rfc-editor.org/info/rfc7181/), and [RFC 7183](https://www.rfc-editor.org/info/rfc7183/). They are references for the *gap*, not protocols implemented by this prototype. A disconnected group cannot guarantee globally unique decisions; recovering the ground link would require reconciling stale and conflicting state.

## What a real deployment would still need

An independent engineering and safety programme would have to establish reliable track provenance and uncertainty, measured communication availability under mobility and interference, authenticated and time-bounded messages, navigation and collision safety, clear human authorization, fail-safe behaviour when information is stale or conflicting, and validation against representative field data. None of those can be inferred from the simulator's favourable cases. The software deliberately has no operational interfaces.

## How to evaluate the hackathon claim

Test across many seeds and all four patterns, including no available interceptors, excess interceptors, late route changes, revised confidence in both directions, changed zone consequence, failed resources, and network partitions. Report the distribution and worst cases, not only the default seed. Compare total and critical leakage, consequence-weighted leakage, resource cost, retasks, unresolved tracks, and peer claim conflicts. A negative improvement must remain visible. That evidence is more credible than claiming the system always outperforms the baseline.
