// Layout RC+: menu lateral (gaveta em telas pequenas, recolhível em telas largas) e tema claro/escuro.
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

  // Recolher/expandir o menu lateral em telas largas; a escolha fica salva no navegador.
  const recolher = document.querySelector("[data-recolher-menu]");
  const rotulos = menu ? menu.querySelectorAll(".navegacao__item") : [];

  function aplicarRecolhido(recolhido) {
    if (recolhido) raiz.dataset.menu = "recolhido";
    else delete raiz.dataset.menu;
    if (recolher) {
      const texto = recolhido ? "Expandir menu" : "Recolher menu";
      recolher.setAttribute("aria-expanded", String(!recolhido));
      recolher.setAttribute("aria-label", texto);
      recolher.title = texto;
    }
    // Com o menu recolhido, o nome de cada item aparece ao passar o mouse.
    rotulos.forEach(function (item) {
      const rotulo = item.querySelector(".navegacao__rotulo");
      if (recolhido && rotulo) item.title = rotulo.textContent.trim();
      else item.removeAttribute("title");
    });
  }

  aplicarRecolhido(raiz.dataset.menu === "recolhido");
  if (recolher) {
    recolher.addEventListener("click", function () {
      const recolhido = raiz.dataset.menu !== "recolhido";
      aplicarRecolhido(recolhido);
      try {
        localStorage.setItem("rc-menu", recolhido ? "recolhido" : "expandido");
      } catch (e) {
        /* armazenamento indisponível: vale só para esta página */
      }
    });
  }

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
