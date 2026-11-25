import React from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import App from "./App.jsx";
import "./site.css";
import "./theme.css";
import "./showcase.css";
import "./admin.css";
import "./mobile.css";

// A picture that fails to load (a cover that is missing or not reachable) shows a tidy placeholder
// instead of a broken-image icon. It runs once per picture, so it can never loop.
const PLACEHOLDER = "data:image/svg+xml;utf8," + encodeURIComponent(
  "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 400 400'>" +
  "<defs><linearGradient id='g' x1='0' y1='0' x2='1' y2='1'><stop offset='0' stop-color='#1b2440'/><stop offset='1' stop-color='#07090f'/></linearGradient></defs>" +
  "<rect width='400' height='400' fill='url(#g)'/>" +
  "<circle cx='200' cy='170' r='92' fill='none' stroke='#c9a063' stroke-width='2' opacity='.55'/>" +
  "<text x='200' y='212' text-anchor='middle' font-family='Georgia,serif' font-size='120' fill='#c9a063'>&#9834;</text>" +
  "<text x='200' y='310' text-anchor='middle' font-family='Georgia,serif' font-size='24' letter-spacing='7' fill='#c9a063'>ZIMBERMANNE</text></svg>");
document.addEventListener("error", (e) => {
  const el = e.target;
  if (el && el.tagName === "IMG" && !el.dataset.fallback) {
    el.dataset.fallback = "1";
    el.src = PLACEHOLDER;
  }
}, true);

createRoot(document.getElementById("root")).render(
  <BrowserRouter>
    <App />
  </BrowserRouter>
);
