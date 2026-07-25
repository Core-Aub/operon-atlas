export const app = document.querySelector("#app");
export const navLinks = [...document.querySelectorAll(".nav a")];

if (!app) {
  throw new Error("Missing #app container");
}
