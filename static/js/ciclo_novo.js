// Prévia do "Novo ciclo anual": mostra os trimestres e bimestres que serão criados
// conforme as caixas marcadas. Sem JavaScript, a prévia fica oculta e o formulário
// funciona normalmente.
(function () {
  var form = document.querySelector("[data-ciclo-novo]");
  var previa = document.querySelector("[data-ciclo-previa]");
  if (!form || !previa) return;

  var MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"];
  var tri = form.querySelector("[name=dividir_trimestres]");
  var bi = form.querySelector("[name=dividir_bimestres]");
  var inicio = form.querySelector("[name=data_inicio]");
  var botao = form.querySelector("[data-ciclo-novo-botao]");

  function mesInicial() {
    // Aceita dd/mm/aaaa (campo de texto) ou aaaa-mm-dd (campo de data).
    var valor = (inicio && inicio.value) || "";
    var br = valor.match(/^\d{1,2}\/(\d{1,2})\/\d{4}$/);
    var iso = valor.match(/^\d{4}-(\d{2})-\d{2}$/);
    var mes = br ? parseInt(br[1], 10) : iso ? parseInt(iso[1], 10) : 1;
    return mes >= 1 && mes <= 12 ? mes - 1 : 0;
  }

  function preencher(lista, meses, letra) {
    var base = mesInicial();
    var total = 12 / meses;
    lista.innerHTML = "";
    for (var i = 0; i < total; i++) {
      var de = MESES[(base + i * meses) % 12];
      var ate = MESES[(base + i * meses + meses - 1) % 12];
      var item = document.createElement("li");
      var forte = document.createElement("strong");
      forte.textContent = letra + (i + 1);
      var periodo = document.createElement("span");
      periodo.className = "texto-suave";
      periodo.textContent = de + " a " + ate;
      item.appendChild(forte);
      item.appendChild(periodo);
      lista.appendChild(item);
    }
  }

  function atualizar() {
    var comTri = tri && tri.checked;
    var comBi = bi && bi.checked;
    previa.querySelector("[data-previa-trimestres]").hidden = !comTri;
    previa.querySelector("[data-previa-bimestres]").hidden = !comBi;
    preencher(previa.querySelector("[data-previa-lista='3']"), 3, "T");
    preencher(previa.querySelector("[data-previa-lista='2']"), 2, "B");
    var total = 1 + (comTri ? 4 : 0) + (comBi ? 6 : 0);
    var partes = ["1 ciclo anual"];
    if (comTri) partes.push("4 trimestrais");
    if (comBi) partes.push("6 bimestrais");
    previa.querySelector("[data-previa-resumo]").textContent =
      partes.join(", ") + " — " + total + (total === 1 ? " ciclo" : " ciclos") + " no total.";
    if (botao) botao.textContent = total === 1 ? "Salvar" : "Criar " + total + " ciclos";
    form.querySelectorAll(".divisao__opcao").forEach(function (opcao) {
      var caixa = opcao.querySelector("input");
      opcao.classList.toggle("divisao__opcao--marcada", !!(caixa && caixa.checked));
    });
  }

  previa.hidden = false;
  [tri, bi, inicio].forEach(function (campo) {
    if (campo) campo.addEventListener("change", atualizar);
  });
  atualizar();
})();
