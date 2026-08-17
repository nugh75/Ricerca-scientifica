type RouteHandler = (params: Record<string, string>) => void;

interface Route {
  segments: string[];
  handler: RouteHandler;
}

const routes: Route[] = [];
let notFoundHandler: () => void = () => {};

export function registerRoute(pattern: string, render: RouteHandler): void {
  routes.push({ segments: pattern.split("/").filter(Boolean), handler: render });
}

export function navigate(path: string): void {
  location.hash = path;
}

function matchAndRender(): void {
  const path = location.hash.replace(/^#/, "") || "/";
  const pathSegments = path.split("/").filter(Boolean);

  for (const route of routes) {
    if (route.segments.length !== pathSegments.length) continue;
    const params: Record<string, string> = {};
    let matched = true;
    for (let i = 0; i < route.segments.length; i++) {
      const seg = route.segments[i];
      if (seg.startsWith(":")) {
        params[seg.slice(1)] = pathSegments[i];
      } else if (seg !== pathSegments[i]) {
        matched = false;
        break;
      }
    }
    if (matched) {
      route.handler(params);
      return;
    }
  }
  notFoundHandler();
}

export function startRouter(_outlet: HTMLElement, notFound: () => void): void {
  notFoundHandler = notFound;
  window.addEventListener("hashchange", matchAndRender);
  matchAndRender();
}
