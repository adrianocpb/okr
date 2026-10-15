// Layout RC+: menu lateral em telas pequenas e alternância de tema claro/escuro.
// Sem JavaScript, o menu fica visível no topo da página e o tema segue o sistema operacional.
(function () {
  "use strict";

  const raiz = document.documentElement;
  const menu = document.getElementById("menu-lateral");
  const fundo = document.querySelector(".menu-lateral__fundo");
  const abrir = document.querySelector("[data-abrir-menu]");

  function definirMenu(aberto) {
    if (!menu) return;
    menu.classList.toggle("menu-lateral--aberto", aberto);
    if (fundo) fundo.hidden = !aberto;
    if (abrir) abrir.setAttribute("aria-expanded", String(aberto));
    if (aberto) {
      const primeiro = menu.querySelector("a, button");
      if (primeiro) primeiro.focus();
    } else if (abrir) {
      abrir.focus();
    }
  }

  if (abrir) abrir.addEventListener("click", function () { definirMenu(true); });
  document.querySelectorAll("[data-fechar-menu]").forEach(function (el) {
    el.addEventListener("click", function () { definirMenu(false); });
  });
  document.addEventListener("keydown", function (evento) {
    if (evento.key === "Escape" && menu && menu.classList.contains("menu-lateral--aberto")) {
      definirMenu(false);
    }
  });

  function temaAtual() {
    if (raiz.dataset.tema) return raiz.dataset.tema;
    return window.matchMedia("(prefers-color-scheme: dark)").matches ? "escuro" : "claro";
  }

  const alternar = document.querySelector("[data-alternar-tema]");
  if (alternar) {
    alternar.addEventListener("click", function () {
      const novo = temaAtual() === "escuro" ? "claro" : "escuro";
      raiz.dataset.tema = novo;
      try {
        localStorage.setItem("rc-tema", novo);
      } catch (e) {
        /* armazenamento indisponível: o tema vale só para esta página */
      }
    });
  }
})();
