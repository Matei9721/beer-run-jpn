export function createMapState() {
  let instance = null;
  return {
    attach(mapInstance) { instance = mapInstance; },
    getInstance: () => instance,
    detach() { instance = null; },
  };
}
