"""klt sim corner-matrix campaigns for the DR-0002 spec rows (issue #62).

This package is the *adapter* between this repo's ratified spec
(``spec/decision-records/0002-target-spec-ratification.md``) and
``klt sim``'s own corner-matrix envelopes. It deliberately does three
narrow things and nothing else:

``build``
    Compose a ``klt sim`` netlist body (the committed schematic DUT,
    ``design/comparator.spice``, inlined verbatim between hash-stamped
    markers, plus one bench circuit from
    ``sim/klt-corner-verification/benches/``) and the matching request
    document.
``run``
    Invoke ``klt sim`` on that request and keep its JSON envelope byte for
    byte, together with the exact invocation. The adapter never edits an
    envelope: what ``klt`` printed is what is committed.
``grade``
    Read committed envelopes and grade every DR-0002 row/sub-bound
    (``sim/klt-corner-verification/rows.json``) literally against its
    Target and Stretch, reporting the binding corner -- and keeping a
    missing measurement, an incomplete grid, a wrong DUT and an
    unsupported reduction distinguishable from a numerical spec miss.

Stdlib only, like ``sim/harness``.
"""
