let currentRouteKey = "";

export function setCurrentRouteKey(routeKey) {
  currentRouteKey = routeKey;
}

export function getCurrentRouteKey() {
  return currentRouteKey;
}

export function isCurrentRoute(routeKey) {
  return currentRouteKey === routeKey;
}
