"""Calendar and location grouping behavior for the trip map."""

from tests.test_frontend import run_node_module


def test_map_days_keep_the_logged_calendar_date_and_filters_do_not_mutate_entries():
    result = run_node_module("""
      import { mapDayKey, mapVisibleEntries } from './src/frontend/app/js/map.js';
      const entries = [
        { id: 3, username: 'Alex', timestamp: '2026-04-02T11:00:00' },
        { id: 2, username: 'Bo', timestamp: '2026-04-01T19:00:00' },
        { id: 1, username: 'Alex', timestamp: '2026-04-01T00:15:00+09:00' },
        { id: 4, username: 'Alex', timestamp: 'invalid' },
      ];
      console.log(JSON.stringify({
        keys: [mapDayKey(entries[2]), mapDayKey(entries[3]), mapDayKey({timestamp:'2026-02-30T12:00:00'})],
        day: mapVisibleEntries(entries, { day:'2026-04-01' }).map(e => e.id),
        both: mapVisibleEntries(entries, { day:'2026-04-01', username:'Alex' }).map(e => e.id),
        runner: mapVisibleEntries(entries, { username:'Alex' }).map(e => e.id),
        all: mapVisibleEntries(entries).map(e => e.id),
        original: entries.map(e => e.id),
      }));
    """)

    assert result == {
        "keys": ["2026-04-01", "", ""],
        "day": [1, 2],
        "both": [1],
        "runner": [1, 3, 4],
        "all": [1, 2, 3, 4],
        "original": [3, 2, 1, 4],
    }


def test_map_stops_bound_distance_and_duration_without_chaining_or_grouping_missing_coordinates():
    result = run_node_module("""
      import { buildMapStops } from './src/frontend/app/js/map.js';
      const entry = (id, timestamp, latitude = 35, longitude = 139) => ({ id, timestamp, latitude, longitude });
      const entries = [
        entry(3, '2026-04-01T12:40:00', 35.0002),
        entry(2, '2026-04-01T11:20:00', 35.0001),
        entry(1, '2026-04-01T10:00:00'),
        entry(4, '2026-04-01T13:00:00', 35.01),
        entry(5, '2026-04-02T13:00:00', 35.01),
        entry(6, '2026-04-02T13:01:00', null),
        entry(7, '2026-04-02T13:01:00', ''),
        entry(8, '2026-04-02T13:02:00', 91),
        entry(9, '2026-04-02T13:03:00', 35.0101),
        entry(10, 'invalid'),
      ];
      const midnight = [entry(11, '2026-04-01T23:59:00'), entry(12, '2026-04-02T00:01:00')];
      console.log(JSON.stringify({
        stops: buildMapStops(entries).map(s => s.entries.map(e => e.id)),
        midnight: buildMapStops(midnight).map(s => s.entries.map(e => e.id)),
      }));
    """)

    assert result["stops"] == [[1, 2], [3], [4], [5, 9], [10]]
    assert result["midnight"] == [[11], [12]]


def test_replay_keeps_chronology_and_revisits_locations_as_separate_stops():
    result = run_node_module("""
      import { buildMapReplay, mapVisibleEntries } from './src/frontend/app/js/map.js';
      const entry = (id, timestamp, username = 'Alex', latitude = 35) =>
        ({ id, timestamp, username, latitude, longitude:139 });
      const entries = [
        entry(4, '2026-04-02T10:00:00'),
        entry(2, '2026-04-01T10:10:00', 'Bo', 35.0001),
        entry(3, '2026-04-01T11:00:00', 'Alex', 36),
        entry(1, '2026-04-01T10:00:00'),
        entry(5, '2026-04-02T11:00:00', 'Alex', null),
      ];
      const plan = buildMapReplay(entries);
      console.log(JSON.stringify({
        ids:plan.map(s => s.entry.id),
        stops:plan.map(s => [s.stopIndex, s.entryIndex, s.stopCount, s.stop.entries.length]),
        sharedStop:plan[0].stop === plan[1].stop,
        filtered:buildMapReplay(mapVisibleEntries(entries, {username:'Alex', day:'2026-04-01'})).map(s => s.entry.id),
        empty:buildMapReplay([]), original:entries.map(e => e.id),
      }));
    """)

    assert result == {
        "ids": [1, 2, 3, 4],
        "stops": [[0, 0, 3, 2], [0, 1, 3, 2], [1, 0, 3, 1], [2, 0, 3, 1]],
        "sharedStop": True,
        "filtered": [1, 3],
        "empty": [],
        "original": [4, 2, 3, 1, 5],
    }


def test_replay_waits_for_arrival_and_cluster_reveal_and_cancels_pending_callbacks():
    result = run_node_module("""
      import { visitMapReplayStop } from './src/frontend/app/js/map.js';
      const run = ({cancelAt = null, emitMove = true, cluster = true, animate = true} = {}) => {
        const timers = new Map(), events = new Map(), calls = [];
        let nextId = 0;
        globalThis.window = {
          setTimeout: (fn, ms) => { timers.set(++nextId, {fn, ms}); return nextId; },
          clearTimeout: id => timers.delete(id),
        };
        const tick = () => { const [id, task] = timers.entries().next().value;
          timers.delete(id); calls.push(['wait',task.ms]); task.fn(); };
        const map = { on:(name,fn) => events.set(name,fn), off:name => events.delete(name),
          flyToBounds:(bounds,options) => calls.push(['fly',bounds,options]) };
        const group = { getVisibleParent: () => cluster ? {spiderfy:() => calls.push('reveal')} : {} };
        const cancel = visitMapReplayStop(map,group,{}, {entries:[{latitude:35,longitude:139}]}, {
          padding:{paddingTopLeft:[20,180],paddingBottomRight:[480,40]}, animate,
          onReady:() => calls.push('ready'),
        });
        if (cancelAt === 'flight') cancel();
        if (emitMove) events.get('moveend')?.();
        if (cancelAt === 'arrival') cancel();
        if (cancelAt === 'reveal') { tick(); cancel(); }
        while (timers.size) tick();
        return {calls,listeners:events.size,timers:timers.size};
      };
      console.log(JSON.stringify({normal:run(), noMove:run({emitMove:false}),
        reduced:run({animate:false}), individual:run({cluster:false}),
        flight:run({cancelAt:'flight'}), arrival:run({cancelAt:'arrival'}), reveal:run({cancelAt:'reveal'})}));
    """)

    fly = ["fly", [[35, 139]], {
        "paddingTopLeft": [20, 180], "paddingBottomRight": [480, 40],
        "maxZoom": 18, "animate": True, "duration": 1.2,
    }]
    assert result["normal"]["calls"] == [fly, ["wait", 350], "reveal", ["wait", 250], "ready"]
    assert result["noMove"]["calls"] == [fly, ["wait", 1600], ["wait", 350], "reveal", ["wait", 250], "ready"]
    assert result["individual"]["calls"] == [fly, ["wait", 350], ["wait", 0], "ready"]
    assert result["reduced"]["calls"][0][2]["animate"] is False
    assert result["reduced"]["calls"][1:] == [["wait", 0], "reveal", ["wait", 0], "ready"]
    assert result["flight"]["calls"] == [fly]
    assert result["arrival"]["calls"] == [fly]
    assert result["reveal"]["calls"] == [fly, ["wait", 350], "reveal"]
    assert all(case["listeners"] == 0 and case["timers"] == 0 for case in result.values())


def test_selection_follows_the_existing_cluster_or_expanded_pin():
    result = run_node_module("""
      import { updateMapSelection } from './src/frontend/app/js/map.js';
      const makeIcon = () => {
        const attrs = {};
        const classes = new Set();
        const icon = { attrs, classes, writes:0, classList: {
          contains: c => classes.has(c),
          toggle: (c, on) => { icon.writes++; on ? classes.add(c) : classes.delete(c); } },
          getAttribute: k => attrs[k] ?? null,
          setAttribute: (k,v) => { icon.writes++; attrs[k]=v; } };
        return icon;
      };
      const layer = (name, count) => ({ name, icon:makeIcon(), options:{ keyboard:true, opacity:1 },
        getElement() { return this.icon; }, ...(count ? { getChildCount: () => count } : {}) });
      const first = layer('first'), second = layer('second'), third = layer('third');
      const cluster = layer('cluster', 80), small = layer('small', 2);
      const layers = [first, second, third, cluster, small];
      const markers = new Map([[1,first], [2,second], [3,third]]);
      const parents = new Map([[first,cluster], [second,cluster], [third,small]]);
      const group = { getVisibleParent: m => parents.get(m) };
      let previous = null;
      const select = id => { previous = updateMapSelection(group, markers, id, previous);
        return layers.filter(l => l.icon?.classes.has('is-selected')).map(l => l.name); };
      const clustered = select(1);
      const sameLocation = select(2);
      const writesBefore = layers.reduce((sum,l) => sum+l.icon.writes,0);
      select(2);
      const redundantWrites = layers.reduce((sum,l) => sum+l.icon.writes,0)-writesBefore;
      const clusterLabel = cluster.icon.attrs['aria-label'];
      // Expanding a cluster reveals its pins and clears the old badge highlight.
      parents.set(first, first);
      parents.set(second, second);
      const revealed = select(1);
      const nextExpandedPin = select(2);
      parents.set(first, cluster);
      parents.set(second, cluster);
      const collapsed = select(2);
      const otherLocation = select(3);
      // Leaflet recreates a cluster's DOM during a zoom animation.
      small.icon = makeIcon();
      const replacedIcon = select(3);
      const pressed = small.icon.attrs['aria-pressed'];
      const closed = select(null);
      const missingEntry = select(99);
      parents.set(third, null);
      const outsideViewport = select(3);
      parents.set(third, third);
      third.icon = null;
      const beforeMount = select(3);
      third.icon = makeIcon();
      const afterMount = select(3);
      console.log(JSON.stringify({ clustered,sameLocation,redundantWrites,clusterLabel,revealed,nextExpandedPin,collapsed,otherLocation,
        replacedIcon,pressed,closed,missingEntry,outsideViewport,beforeMount,afterMount,
        originalPinsUsable: [...markers.values()].every(m => m.options.keyboard && m.options.opacity === 1),
        noHiddenPins: layers.every(l => !l.icon?.attrs['aria-hidden']) }));
    """)

    assert result == {
        "clustered": ["cluster"],
        "sameLocation": ["cluster"],
        "redundantWrites": 0,
        "clusterLabel": "80 drinks",
        "revealed": ["first"],
        "nextExpandedPin": ["second"],
        "collapsed": ["cluster"],
        "otherLocation": ["small"],
        "replacedIcon": ["small"],
        "pressed": "true",
        "closed": [],
        "missingEntry": [],
        "outsideViewport": [],
        "beforeMount": [],
        "afterMount": ["third"],
        "originalPinsUsable": True,
        "noHiddenPins": True,
    }


def test_clusters_expand_to_individual_pins_when_local_or_at_maximum_zoom():
    result = run_node_module("""
      import { expandMapCluster } from './src/frontend/app/js/map.js';
      const run = (distance, zoom) => {
        const calls = [];
        const padding = { paddingTopLeft:[20,180], paddingBottomRight:[380,40] };
        const map = { distance: () => distance, getZoom: () => zoom, getMaxZoom: () => 19,
          project: value => ({ add: offset => value.map((n,i) => n+offset[i]) }),
          unproject: value => value, panTo: value => calls.push({ centre:value }) };
        const cluster = {
          getBounds: () => ({ getNorthWest: () => [35,139], getSouthEast: () => [35.1,139.1] }),
          getLatLng: () => [1000,2000],
          zoomToBounds: value => calls.push({ zoom:value }),
          spiderfy: () => calls.push('spiral'),
        };
        const getPadding = () => { calls.push('measure'); return padding; };
        const prepare = () => { calls.push('prepare'); padding.paddingBottomRight=[400,80]; };
        return { expanded:expandMapCluster(map,cluster,getPadding,prepare), calls };
      };
      console.log(JSON.stringify({ nearby:run(60,16), boundary:run(120,16),
        wide:run(1200,10), maximum:run(1200,19) }));
    """)

    expanded = {"expanded": True, "calls": ["prepare", "measure", {"centre": [1190, 1950]}, "spiral"]}
    assert result["nearby"] == expanded
    assert result["boundary"] == expanded
    assert result["maximum"] == expanded
    assert result["wide"] == {
        "expanded": False,
        "calls": ["measure", {"zoom": {"paddingTopLeft": [20, 180], "paddingBottomRight": [380, 40]}}],
    }
