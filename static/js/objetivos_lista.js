// Lista de objetivos: botões para expandir ou recolher todas as linhas.
// Sem JavaScript, cada linha continua abrindo e fechando individualmente (<details>).
(function () {
  "use strict";

  const controles = document.querySelector("[data-controles-expansao]");
  if (!controles) return;

  const linhas = document.querySelectorAll("details.objetivo-linha");

  function definir(aberto) {
    linhas.forEach(function (linha) {
      linha.open = aberto;
    });
  }

  controles.querySelector("[data-expandir-todos]").addEventListener("click", function () {
    definir(true);
  });
  controles.querySelector("[data-recolher-todos]").addEventListener("click", function () {
    definir(false);
  });
  controles.hidden = false;
})();
