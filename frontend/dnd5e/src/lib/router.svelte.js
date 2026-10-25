// Hash routes: #/ (list), #/c/<id>/builder/<step>, #/c/<id>/sheet/<tab>, #/campaigns[/<id>], #/equipment[/<item id>].
export const route = $state({ view: "list", id: null, step: null });

function parse() {
  const parts = location.hash.replace(/^#\/?/, "").split("/").filter(Boolean);
  if (parts[0] === "c" && parts[1]) {
    route.view = parts[2] === "sheet" ? "sheet" : parts[2] === "print" ? "print" : "builder";
    route.id = parts[1];
    route.step = parts[3] || null;
  } else if (["campaigns", "equipment", "rules"].includes(parts[0])) {
    route.view = parts[0];
    route.id = null;
    route.step = parts[1] || null;
  } else {
    route.view = "list";
    route.id = null;
    route.step = null;
  }
}

window.addEventListener("hashchange", parse);
parse();

export function go(path) {
  location.hash = path;
}
