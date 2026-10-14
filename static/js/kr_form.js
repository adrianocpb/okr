// Formulário de KR: mostra apenas os campos usados pelo tipo de medição escolhido.
// Sem JavaScript, todos os campos aparecem e o servidor descarta os que não se aplicam.
(function () {
  "use strict";

  const formulario = document.querySelector("[data-formulario-kr]");
  if (!formulario) return;

  const opcoesTipo = formulario.querySelectorAll('input[name="tipo_medicao"]');
  const blocos = formulario.querySelectorAll(".campo[data-tipos]");

  function atualizar() {
    const marcado = formulario.querySelector('input[name="tipo_medicao"]:checked');
    const tipo = marcado ? marcado.value : null;
    blocos.forEach(function (bloco) {
      const tipos = bloco.dataset.tipos.split(" ");
      bloco.hidden = !tipo || !tipos.includes(tipo);
    });
  }

  opcoesTipo.forEach(function (opcao) {
    opcao.addEventListener("change", atualizar);
  });
  atualizar();
})();
