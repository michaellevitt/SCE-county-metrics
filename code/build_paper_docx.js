const fs = require("fs");
const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell, ImageRun,
  AlignmentType, LevelFormat, HeadingLevel, BorderStyle, WidthType, ShadingType,
  PageNumber, Header, Footer, PageBreak, LineNumberRestartFormat
} = require("docx");

const ROOT = "/Users/levitt/Dropbox/win1_DB/NewProjects25/++SCE_USCounties,States_Clean/SCE_USCounties,States_SANDBOX6";
const FIG = ROOT + "/figures_2745";
const OUT = ROOT + "/DRAFT_PAPER_SCE_county_metrics.docx";

const CW = 9360; // content width DXA (US Letter, 1" margins)
const border = { style: BorderStyle.SINGLE, size: 1, color: "BBBBBB" };
const borders = { top: border, bottom: border, left: border, right: border };
const HEAD = "D5E8F0";

function H1(t){return new Paragraph({heading:HeadingLevel.HEADING_1,children:[new TextRun(t)]});}
function H2(t){return new Paragraph({heading:HeadingLevel.HEADING_2,children:[new TextRun(t)]});}
function P(runs){ // runs: array of [text, opts]
  return new Paragraph({spacing:{after:120},children:runs.map(r=>new TextRun(typeof r==="string"?{text:r}:r))});
}
function body(t){return P([t]);}
function bullet(t,ital){
  // accept either a string or an array of runs (objects/strings); an array was
  // previously wrapped in a single TextRun and rendered as an EMPTY bullet.
  const kids = Array.isArray(t)
    ? t.map(r=>new TextRun(typeof r==="string"?{text:r}:r))
    : [new TextRun(typeof t==="string"?{text:t,italics:!!ital}:t)];
  return new Paragraph({numbering:{reference:"bullets",level:0},spacing:{after:60},children:kids});
}
function numItem(runs,ref){return new Paragraph({numbering:{reference:ref||"nums",level:0},spacing:{after:60},
  children:runs.map(r=>new TextRun(typeof r==="string"?{text:r}:r))});}

// Front-matter helpers
function caption(label, text){ // bold "Table N. <caption>"
  return new Paragraph({spacing:{before:160,after:80},children:[
    new TextRun({text:label+". ",bold:true,size:24}),new TextRun({text:text,size:24})]});
}

function cell(text,{head=false,w=CW/2,bold=false,align=AlignmentType.LEFT}={}){
  return new TableCell({
    borders, width:{size:w,type:WidthType.DXA},
    shading: head?{fill:HEAD,type:ShadingType.CLEAR}:undefined,
    margins:{top:60,bottom:60,left:110,right:110},
    children:[new Paragraph({alignment:align,children:
      String(text).split("\n").map((line,li)=>new TextRun(
        li===0?{text:line,bold:bold||head,size:20}:{text:line,bold:bold||head,size:20,break:1}))})]
  });
}
// a cell whose content is several left-aligned lines (one Paragraph each)
function multiCell(paras,{head=false,w=CW/2}={}){
  return new TableCell({
    borders, width:{size:w,type:WidthType.DXA},
    shading: head?{fill:HEAD,type:ShadingType.CLEAR}:undefined,
    margins:{top:60,bottom:60,left:110,right:110},
    children: paras.map(p=>new Paragraph({alignment:AlignmentType.LEFT,spacing:{after:20},
      children:[new TextRun({text:p.t,size:20,italics:!!p.i,bold:!!p.b})]}))
  });
}
function tableFrom(widths, rows){
  return new Table({
    width:{size:widths.reduce((a,b)=>a+b,0),type:WidthType.DXA},
    columnWidths:widths,
    rows: rows.map((r,ri)=>new TableRow({children:r.map((c,ci)=>
      cell(c,{head:ri===0,w:widths[ci],align: ci===0?AlignmentType.LEFT:AlignmentType.CENTER}))}))
  });
}
function figureAt(fullpath,wpx,label,caption){
  const im=fs.readFileSync(fullpath);
  const ext=fullpath.split(".").pop().toLowerCase();
  return [
    new Paragraph({alignment:AlignmentType.CENTER,spacing:{before:120,after:60},children:[
      new ImageRun({type:ext,data:im,transformation:{width:wpx.w,height:wpx.h},
        altText:{title:label,description:caption,name:label}})]}),
    new Paragraph({alignment:AlignmentType.CENTER,spacing:{after:160},children:[
      new TextRun({text:label+". ",bold:true,size:18}),new TextRun({text:caption,italics:true,size:18})]})
  ];
}
function figure(file,wpx,label,caption){
  const im=fs.readFileSync(FIG+"/"+file);
  const ext=file.split(".").pop().toLowerCase();
  return [
    new Paragraph({alignment:AlignmentType.CENTER,spacing:{before:120,after:60},children:[
      new ImageRun({type:ext,data:im,transformation:{width:wpx.w,height:wpx.h},
        altText:{title:label,description:caption,name:label}})]}),
    new Paragraph({alignment:AlignmentType.CENTER,spacing:{after:160},children:[
      new TextRun({text:label+". ",bold:true,size:18}),new TextRun({text:caption,italics:true,size:18})]})
  ];
}

// ===== Table definitions (relocated to the end) =====
const TABLE1 = tableFrom([1100,5800,1230,1230],[
  ["Super Cluster","Name","# clusters","# variables"],
  ["1","Race, Ethnicity and Population by Age","16","463"],
  ["2","Geography, Environment and Housing","6","88"],
  ["3","Socioeconomic, Insurance and Demographic Characteristics","14","412"],
  ["4","Vital Statistics and Total Physician Counts","5","88"],
  ["5","Poverty, Insurance Coverage and Public Programs","7","175"],
  ["6","Primary Care, Generalist and Diagnostic Physicians","29","590"],
  ["7","Surgical, Procedural and Specialty Physicians","17","266"],
  ["8","Commuting and Industry Employment","2","48"],
  ["9","Aggregate Physician and Facility Totals","10","180"],
  ["10","Hospital Telehealth and Advanced Imaging Services","2","43"],
  ["11","Hospital Capacity and Nursing and Allied Staffing","12","374"],
]);
// Main Table 1: super-cluster significance summary under the |CC| bands.
// Counts are variables whose maximum |CC| over the all-age years 2020–2024 falls in each band
// (population-weighted, NORMED); computed from full_w1.0/metric_x_death_cc_1.0_0.csv joined to
// the k=120 cluster→super-cluster assignments. Sorted by % with |CC| > 0.3, descending.
const TABLE_SCSIG = tableFrom([720,2120,540,700,700,560,560,2840,620],[
  ["Super Cluster ID","Super-cluster","Total variables","Moderate 0.30<|CC|<0.45","Strong |CC|>0.45","% |CC|>0.30","Mean |CC|","Strongest variable","CC (year)"],
  ["3","Socioeconomic, Insurance and Demographic Characteristics","412","106","50","37.9","0.270","% adults 25+ with 4+ yr college, White non-Hisp.","−0.54\n(2021)"],
  ["5","Poverty, Insurance Coverage and Public Programs","175","42","18","34.3","0.232","% adults 40–64 without health insurance","+0.52\n(2021)"],
  ["8","Commuting and Industry Employment","48","10","5","31.2","0.224","% population did not work, 16–64","+0.50\n(2021)"],
  ["1","Race, Ethnicity and Population by Age","463","112","4","25.1","0.218","Hispanic/Latino (Ecuadorian) population","+0.50\n(2020)"],
  ["2","Geography, Environment and Housing","88","15","0","17.0","0.188","Owner-occupied housing units (count)","−0.43\n(2020)"],
  ["9","Aggregate Physician and Facility Totals","180","23","0","12.8","0.153","Medical-specialty physicians, 45–54","−0.37\n(2021)"],
  ["4","Vital Statistics and Total Physician Counts","88","11","0","12.5","0.147","Total M.D.s aged 55–64","−0.37\n(2021)"],
  ["6","Primary Care, Generalist and Diagnostic Physicians","590","52","0","8.8","0.155","Inactive female medical doctors","−0.42\n(2021)"],
  ["7","Surgical, Procedural and Specialty Physicians","266","18","0","6.8","0.169","Psychiatrists, 55–64","−0.33\n(2021)"],
  ["11","Hospital Capacity and Nursing and Allied Staffing","374","6","0","1.6","0.091","Education/health/social-assistance workers (count)","−0.36\n(2021)"],
  ["10","Hospital Telehealth and Advanced Imaging Services","43","0","0","0.0","0.077","Hispanic/Latino (all other), hospital pop.","+0.26\n(2020)"],
]);
const TABLE3 = tableFrom([2600,1300,1500,1500,2460],[
  ["Comparison","Changed variables","Moderate in both","Neither in both","Agreement"],
  ["2015 vs 2019","1,617","284","1,305","98.3%"],
  ["2019 vs 2023–2024","1,971","230","1,634","94.6%"],
]);
const T2_ROWS = [
  {year:"2020", theme:"First-wave geography — morbidity, large households, transit exposure, poverty:",
   mets:["Inpatient per-capita Medicare cost (+)",
         "% persons 25+ with high-school diploma or more (−)",
         "# workers 16+ using public transportation (+)",
         "# households with 5 persons (+)",
         "% persons in poverty (+)"], r2:"0.48", cv:"0.46"},
  {year:"2021", theme:"Socioeconomic gradient — education, affluence, employment:",
   mets:["% persons 25+ with 4+ yr college, White non-Hisp. (−)",
         "county population (estimate) (+)",
         "ratio of income to poverty ≥ 2.0 (−)",
         "non-veterans 25+ with high-school diploma or more (−)",
         "% population not working, 16–64 (+)"], r2:"0.42", cv:"0.41"},
];
const TABLE4 = new Table({width:{size:9360,type:WidthType.DXA},columnWidths:[760,6500,1050,1050],
  rows:[
    new TableRow({children:[
      cell("Year",{head:true,w:760,align:AlignmentType.CENTER}),
      cell("Theme and the five variables selected (sign of CC)",{head:true,w:6500}),
      cell("R²",{head:true,w:1050,align:AlignmentType.CENTER}),
      cell("CV R²",{head:true,w:1050,align:AlignmentType.CENTER})]}),
    ...T2_ROWS.map(r=>new TableRow({children:[
      cell(r.year,{w:760,align:AlignmentType.CENTER}),
      multiCell([{t:r.theme,i:true},...r.mets.map(m=>({t:"• "+m}))],{w:6500}),
      cell(r.r2,{w:1050,align:AlignmentType.CENTER}),
      cell(r.cv,{w:1050,align:AlignmentType.CENTER})]}))
  ]});
const TABLE5 = tableFrom([1800,2520,2520,2520],[
  ["Year","max single |CC|","mean excess-death fraction","5-variable CV R²"],
  ["2020","0.50","+0.19","0.47"],
  ["2021","0.54","+0.20","0.42"],
  ["2022","0.36","+0.11","0.21"],
  ["2023","0.30","+0.03","0.18"],
  ["2024","0.36","−0.01","0.22"],
]);
const TABLE6 = tableFrom([3360,2000,2000,2000],[
  ["Outcome","linear-5","ridge (all ~150)","gradient boosting"],
  ["2020","0.42","0.43","0.47"],
  ["2021","0.38","0.26","0.41"],
  ["2022–2024","0.14–0.17","0.10–0.12","0.15–0.18"],
  ["2020–2023 cumulative","0.23","0.19","0.19"],
]);
const TABLE7 = tableFrom([900,1300,1100,1300,1500,1200,2060],[
  ["Year","# moderate","PC1 var%","PC1 R²","PC1+PC2 R²","CV perf.","PC1 meaning"],
  ["2021","220","42%","0.32","0.40","0.41","education (−), MD supply (−): SES gradient"],
  ["2020","241","55%","0.23","0.29","0.46","Hispanic/Latino share (+): ethnicity axis"],
]);

// Table S6: each super-cluster and its constituent cluster (semantic) names.
// Built from the supplementary TSV so the paper and the data file stay in sync.
function buildTableS6(){
  const lines = fs.readFileSync(ROOT+"/Supplementary_Tables_Figures/Table_S3_supercluster_cluster_names.tsv","utf8")
    .trim().split("\n").slice(1);
  const groups=[]; let cur=null;
  for(const ln of lines){
    const c=ln.split("\t");
    if(c[0]&&c[0].trim()){ cur={sc:c[0].trim(),name:c[1].trim(),labels:[]}; groups.push(cur); }
    if(cur&&c[3]&&c[3].trim()) cur.labels.push(c[3].trim());
  }
  const widths=[760,2400,6200];
  const header=new TableRow({children:[
    cell("Super Cluster",{head:true,w:760,align:AlignmentType.CENTER}),
    cell("Name",{head:true,w:2400}),
    cell("Constituent clusters (semantic labels)",{head:true,w:6200})]});
  const rows=groups.map(g=>new TableRow({children:[
    cell(g.sc,{w:760,align:AlignmentType.CENTER}),
    cell(g.name,{w:2400}),
    multiCell(g.labels.map(l=>({t:l})),{w:6200})]}));
  return new Table({width:{size:9360,type:WidthType.DXA},columnWidths:widths,rows:[header,...rows]});
}
const TABLE_S6 = buildTableS6();

// Table S7: top six significant (|CC| > 0.3) DISTINCT variables per super-cluster (deduplicated to
// one representative — the highest-|CC| member — per k=120 semantic cluster). From the computed TSV.
// Variable names are the AHRF explain text with the trailing "=<year>" stripped and underscores
// turned to spaces (kept otherwise verbatim, including source spellings). The "Collapsed" column
// is the number of OTHER significant variables in the same cluster that the representative stands for
// (their names are enumerated in Table_S4A_collapsed_variants.tsv).
function cleanMetric(s){
  return String(s).replace(/=.*/,"").replace(/_/g," ").replace(/\s+/g," ").trim();
}
function buildTableS7(){
  const lines = fs.readFileSync(ROOT+"/Supplementary_Tables_Figures/Table_S4_top6_metrics_per_supercluster.tsv","utf8")
    .trim().split("\n").slice(1);
  const SC_NMETRICS={1:463,2:88,3:412,4:88,5:175,6:590,7:266,8:48,9:180,10:43,11:374};
  const rows=[["SC","Super-cluster (# variables)","#","Representative variable","CC","Yr","Collapsed"]];
  for(const ln of lines){
    const c=ln.split("\t"); // SC, Super-cluster, Rank, Variable(explain), metric_code, CC, year, n_collapsed
    const variable = c[3]==="(none significant)" ? "(none reaching the moderate band)" : cleanMetric(c[3]);
    const scname = c[1] ? c[1]+" ("+SC_NMETRICS[parseInt(c[0],10)]+")" : c[1];
    rows.push([c[0], scname, c[2], variable, c[5]||"", c[6]||"", c[7]||""]);
  }
  return tableFrom([380,1860,360,4360,640,760,1000],rows);
}
const TABLE_S7 = buildTableS7();

// Table S8: significant-variable counts and max |CC| by year and age band, from the computed TSV.
function buildTableS8(){
  const lines = fs.readFileSync(ROOT+"/Supplementary_Tables_Figures/Table_S5_age_band_divergence.tsv","utf8")
    .trim().split("\n").slice(1);
  const rows=[["Year","# sig (all)","# sig (<65)","# sig (≥65)","max|CC| (all)","max|CC| (<65)","max|CC| (≥65)"]];
  for(const ln of lines) rows.push(ln.split("\t"));
  return tableFrom([900,1250,1300,1300,1450,1500,1660],rows);
}
const TABLE_S8 = buildTableS8();

// Table S9: variable vintage composition of the two AHRF releases, from the computed TSV.
function buildTableS9(){
  const lines = fs.readFileSync(ROOT+"/Supplementary_Tables_Figures/Table_S6_vintage_composition.tsv","utf8")
    .trim().split("\n").slice(1);
  const rows=[["Data year","≤2015 vintage","≤2019 vintage (main)","2023–2024 vintage"]];
  for(const ln of lines) rows.push(ln.split("\t"));
  return tableFrom([2340,2340,2340,2340],rows);
}
const TABLE_S9 = buildTableS9();
const TABLE_WEIGHT = tableFrom([900,2200,820,1230,1230,1340,1040],[
  ["Weight power p","County weighting","N_eff","% |CC|>0.30","% |CC|>0.45","Median max |CC|","Max |CC|"],
  ["0","Unweighted","3,139","0.3%","0%","0.066","0.370"],
  ["0.5","Square-root of population","1,595","4.3%","0%","0.107","0.440"],
  ["0.75","Population^0.75","712","10.6%","1.0%","0.131","0.491"],
  ["1.0","Full population (primary)","282","17.3%","2.8%","0.156","0.543"],
]);

// superscript helper for affiliations
function sup(n){return new TextRun({text:n,superScript:true,size:22});}
// in-text citation superscript marker
function cite(n){return {text:" ("+String(n).replace(/,/g,", ")+")",size:24};}

// ===== REFERENCES (28 entries, hanging indent, literal numbering) =====
const REF_TEXTS = [
  "A. C. Stokes, D. J. Lundberg, I. T. Elo, K. Hempstead, J. Bor, S. H. Preston, COVID-19 and excess mortality in the United States: A county-level analysis. PLoS Med. 18, e1003571 (2021).",
  "M. Karmakar, P. M. Lantz, R. Tipirneni, Association of social and demographic factors with COVID-19 incidence and death rates in the US. JAMA Netw. Open 4, e2036462 (2021).",
  "J. T. Chen, N. Krieger, Revealing the unequal burden of COVID-19 by income, race/ethnicity, and household crowding: US county versus ZIP code analyses. J. Public Health Manag. Pract. 27, S43–S56 (2021).",
  "R. B. Hawkins, E. J. Charles, J. H. Mehaffey, Socio-economic status and COVID-19–related cases and fatalities. Public Health 189, 129–134 (2020).",
  "I. M. Karaye, J. A. Horney, The impact of social vulnerability on COVID-19 in the U.S.: An analysis of spatially varying relationships. Am. J. Prev. Med. 59, 317–325 (2020).",
  "R. K. Wadhera, P. Wadhera, P. Gaba, J. F. Figueroa, K. E. Joynt Maddox, R. W. Yeh, C. Shen, Variation in COVID-19 hospitalizations and deaths across New York City boroughs. JAMA 323, 2192–2195 (2020).",
  "S. B. Tan, P. deSouza, M. Raifman, Structural racism and COVID-19 in the USA: A county-level empirical analysis. J. Racial Ethn. Health Disparities 9, 236–246 (2022).",
  "C. Bambra, R. Riordan, J. Ford, F. Matthews, The COVID-19 pandemic and health inequalities. J. Epidemiol. Community Health 74, 964–968 (2020).",
  "C. J. Patel, J. P. A. Ioannidis, A. K. Manrai, An atlas of exposome-phenome associations in health and disease risk. Nat. Med. 32, 1501–1510 (2026).",
  "L. Y. M. Middleton, E. Walker, S. Cockell, J. Dou, V. K. Nguyen, M. Schrank, C. J. Patel, E. B. Ware, J. A. Colacino, S. K. Park, K. M. Bakulski, Exposome-wide association study of cognition among older adults in the National Health and Nutrition Examination Survey. Exposome 5, osaf002 (2025).",
  "A. K. Manrai, J. P. A. Ioannidis, C. J. Patel, Signals among signals: Prioritizing nongenetic associations in massive data sets. Am. J. Epidemiol. 188, 846–850 (2019).",
  "S. Klau, S. Hoffmann, C. J. Patel, J. P. A. Ioannidis, A.-L. Boulesteix, Examining the robustness of observational associations to model, measurement and sampling uncertainty with the vibration of effects framework. Int. J. Epidemiol. 50, 266–278 (2021).",
  "C. Vinatier, S. Hoffmann, C. Patel, N. J. DeVito, I. A. Cristea, B. Tierney, J. P. A. Ioannidis, F. Naudet, What is the vibration of effects? BMJ Evid. Based Med. 30, 61–65 (2025).",
  "J. P. A. Ioannidis, Infection fatality rate of COVID-19 inferred from seroprevalence data. Bull. World Health Organ. 99, 19–33F (2021).",
  "Health Resources and Services Administration, Area Health Resources Files (AHRF) (US Department of Health and Human Services, Bureau of Health Workforce, Rockville, MD, 2019–2024). https://data.hrsa.gov/topics/health-workforce/ahrf. Accessed 12 June 2026.",
  "A. J. H. Kind, W. R. Buckingham, Making neighborhood-disadvantage variables accessible — The Neighborhood Atlas. N. Engl. J. Med. 378, 2456–2458 (2018).",
  "Centers for Disease Control and Prevention, National Center for Health Statistics, Underlying Cause of Death, 1999–2023, CDC WONDER Online Database (US Department of Health and Human Services, 2024). https://wonder.cdc.gov. Accessed 12 June 2026.",
  "N. Reimers, I. Gurevych, \"Sentence-BERT: Sentence embeddings using Siamese BERT-networks\" in Proceedings of EMNLP-IJCNLP 2019 (Association for Computational Linguistics, Hong Kong, 2019), pp. 3982–3992.",
  "K. Song, X. Tan, T. Qin, J. Lu, T.-Y. Liu, \"MPNet: Masked and permuted pre-training for language understanding\" in Advances in Neural Information Processing Systems 33 (NeurIPS 2020) (Curran Associates, 2020).",
  "J. H. Ward Jr., Hierarchical grouping to optimize an objective function. J. Am. Stat. Assoc. 58, 236–244 (1963).",
  "P. J. Rousseeuw, Silhouettes: A graphical aid to the interpretation and validation of cluster analysis. J. Comput. Appl. Math. 20, 53–65 (1987).",
  "L. Kish, Survey Sampling (John Wiley & Sons, New York, 1965).",
  "R. A. Hummer, E. M. Hernández, The effect of educational attainment on adult mortality in the United States. Popul. Bull. 68, 1–16 (2013).",
  "R. Chetty, M. Stepner, S. Abraham, S. Lin, B. Scuderi, N. Turner, A. Bergeron, D. Cutler, The association between income and life expectancy in the United States, 2001–2014. JAMA 315, 1750–1766 (2016).",
  "S. Woolhandler, D. U. Himmelstein, The relationship of health insurance and mortality: Is lack of insurance deadly? Ann. Intern. Med. 167, 424–431 (2017).",
  "B. Starfield, L. Shi, J. Macinko, Contribution of primary care to health systems and health. Milbank Q. 83, 457–502 (2005).",
  "T. Andrasfay, N. Goldman, Reductions in 2020 US life expectancy due to COVID-19 and the disproportionate impact on the Black and Latino populations. Proc. Natl. Acad. Sci. U.S.A. 118, e2014746118 (2021).",
  "W. S. Robinson, Ecological correlations and the behavior of individuals. Am. Sociol. Rev. 15, 351–357 (1950).",
];
const REFERENCES = REF_TEXTS.map((t,i)=>new Paragraph({
  spacing:{after:60}, indent:{left:480,hanging:480},
  children:[ new TextRun({text:(i+1)+".\t"}), new TextRun({text:t}) ]
}));

const doc = new Document({
  styles:{
    default:{
      document:{
        run:{font:"Times New Roman",size:24},
        paragraph:{spacing:{line:480,lineRule:"auto"}}
      }
    },
    paragraphStyles:[
      {id:"Heading1",name:"Heading 1",basedOn:"Normal",next:"Normal",quickFormat:true,
       run:{size:28,bold:true,font:"Times New Roman",color:"000000"},
       paragraph:{spacing:{before:280,after:160},outlineLevel:0}},
      {id:"Heading2",name:"Heading 2",basedOn:"Normal",next:"Normal",quickFormat:true,
       run:{size:24,bold:true,font:"Times New Roman",color:"000000"},
       paragraph:{spacing:{before:200,after:120},outlineLevel:1}},
    ]
  },
  numbering:{config:[
    {reference:"bullets",levels:[{level:0,format:LevelFormat.BULLET,text:"•",alignment:AlignmentType.LEFT,
      style:{paragraph:{indent:{left:540,hanging:280}}}}]},
    {reference:"nums",levels:[{level:0,format:LevelFormat.DECIMAL,text:"%1.",alignment:AlignmentType.LEFT,
      style:{paragraph:{indent:{left:540,hanging:280}}}}]},
    {reference:"nums2",levels:[{level:0,format:LevelFormat.DECIMAL,text:"%1.",alignment:AlignmentType.LEFT,
      style:{paragraph:{indent:{left:540,hanging:280}}}}]},
    {reference:"nums3",levels:[{level:0,format:LevelFormat.DECIMAL,text:"%1.",alignment:AlignmentType.LEFT,
      style:{paragraph:{indent:{left:540,hanging:280}}}}]},
  ]},
  sections:[{
    properties:{page:{size:{width:12240,height:15840},margin:{top:1440,right:1440,bottom:1440,left:1440}},lineNumbers:{countBy:1,restart:LineNumberRestartFormat.CONTINUOUS,distance:360}},
    footers:{default:new Footer({children:[new Paragraph({alignment:AlignmentType.RIGHT,
      children:[new TextRun({text:"Page ",size:18}),new TextRun({children:[PageNumber.CURRENT],size:18})]})]})},
    children:[
      // ===== FRONT MATTER =====
      new Paragraph({alignment:AlignmentType.CENTER,spacing:{after:160},children:[new TextRun({
        text:"Large-scale assessment of socioeconomic, demographic and health system structures with US county excess mortality, 2020–2024",
        bold:true,size:32,color:"000000"})]}),

      // Authors
      new Paragraph({alignment:AlignmentType.CENTER,spacing:{after:120},children:[
        new TextRun({text:"Michael Levitt",size:24}),sup("1"),
        new TextRun({text:", Ben Marten",size:24}),sup("2"),
        new TextRun({text:", Gal Oren",size:24}),sup("1,3"),
        new TextRun({text:", John P.A. Ioannidis",size:24}),sup("4,5,6,7")]}),

      // Affiliations
      new Paragraph({alignment:AlignmentType.LEFT,spacing:{after:160},children:[
        sup("1"),new TextRun({text:"Department of Structural Biology, Stanford University School of Medicine, Stanford, California, USA; ",size:22}),
        sup("2"),new TextRun({text:"Mortality.Watch, St. Petersburg, Florida, USA; ",size:22}),
        sup("3"),new TextRun({text:"Computer Science Department, Technion Israel Institute of Technology, Haifa, Israel; ",size:22}),
        sup("4"),new TextRun({text:"Meta-Research Innovation Center at Stanford (METRICS), Stanford University School of Medicine, Stanford, California, USA; ",size:22}),
        sup("5"),new TextRun({text:"Stanford Prevention Research Center, Department of Medicine, Stanford University School of Medicine, Stanford, California, USA; ",size:22}),
        sup("6"),new TextRun({text:"Department of Epidemiology and Population Health, Stanford University School of Medicine, Stanford, California, USA; ",size:22}),
        sup("7"),new TextRun({text:"Department of Biomedical Data Science, Stanford University School of Medicine, Stanford, California, USA",size:22})]}),

      P([{text:"Funding: ",bold:true},"National Institutes of Health R35 GM122543 (ML) and NIEHS R01ES032470 (JPAI) and N000142412687 by the Office of Naval Research (JPAI)."]),
      P([{text:"Data and code availability: ",bold:true},"[GitHub repository URL to be added]"]),
      P([{text:"Disclosures: ",bold:true},"The authors have no conflicts of interest."]),
      P([{text:"Acknowledgments: ",bold:true},"None"]),
      P([{text:"Keywords: ",bold:true},"COVID-19, excess mortality, US counties, social determinants, Area Health Resources File, dimensionality"]),

      new Paragraph({children:[new PageBreak()]}),

      // ===== ABSTRACT =====
      new Paragraph({spacing:{before:120,after:120},children:[new TextRun({text:"Abstract",bold:true,size:28})]}),
      body("Socioeconomic, demographic, and health system structural features have been claimed to shape the impact of the COVID-19 pandemic across populations, but past analyses have typically examined only a few factors each time. We aimed to examine systematically how county characteristics covary with COVID-era excess mortality, considering 2,745 county-level variables pertaining to demography, race/ethnicity, income, insurance, education, employment, housing, and the full physician and hospital workforce. Correlation coefficients (CCs) were obtained for these variables (the most recent available value until 2019) against an age-standardized county excess-death measure for every pandemic year 2020–2024 under population weighting. The variables could be grouped by meaning into 11 semantic super-clusters. ~17.3% of variables reached at least a moderate correlation level (|CC| > 0.30) and 2.8% reached strong correlations (|CC| > 0.45). The strongest correlations were seen for college attainment (CC −0.54), uninsurance among adults 40–64 (+0.53), and high income (−0.53). At least moderate correlations were seen for 9.1% of variables in 2020 and 8.5% of variables in 2021, but only 1.8%, 0%, and 1.3% in 2022, 2023, and 2024, respectively. Similar patterns of concentration of at least moderate correlations in the first two pandemic years were seen in both elderly and non-elderly populations. Most variables reaching at least a moderate correlation (362 of 472) and all 77 reaching a strong correlation belonged to the demography and socioeconomic super-clusters. Health-system variables were much weaker — of 1,541 health-system variables (hospital capacity, physician counts and workforce) only 7% reached |CC| > 0.30, versus 31% of the 1,186 socioeconomic and demographic variables. Using the most recent available value until 2022 or 2015 instead of 2019 yielded largely similar results. Overall, these ecological analyses suggest a strong relationship of socioeconomic structure and demographics rather than healthcare-resources/supply with pandemic excess mortality across US counties especially during 2020-2021."),
      // ===== SIGNIFICANCE STATEMENT =====
      new Paragraph({spacing:{before:200,after:120},children:[new TextRun({text:"SIGNIFICANCE STATEMENT",bold:true,size:28})]}),
      body("COVID-19 mortality has been linked to poverty, race, and care access, and other diverse socioeconomic and population factors, but typically only a few factors have been assessed and reported each time. Screening the entire Area Health Resources File — 2,745 unselected county-level variables — we found excess death was ecologically associated with many variables (one out of six had absolute correlations > 0.30). Correlations reflected more strongly variables pertaining to demographics and socioeconomic structure rather than baseline hospital capacity or physician supply. The substantive correlation signals were seen almost exclusively in 2020 and 2021, but not in subsequent years."),

      new Paragraph({children:[new PageBreak()]}),

      // ===== INTRODUCTION =====
      H1("INTRODUCTION"),
      P(["The COVID-19 pandemic demonstrated large geographical variability in its footprint and revealed the high vulnerability of populations with disadvantaged status. County-level analyses of COVID-19 mortality have repeatedly implicated poverty, race, lack of insurance, and poor health-care access as correlates of adverse outcome",cite("1–8"),", but the literature is fragmented. Each study has typically picked only a handful of predictors; moreover, conclusions can hinge on what analyses are performed and reported."]),
      P(["There is increasing interest in studying epidemiological exposures comprehensively at large scale, extending the omics paradigm that is dominant in genetics to diverse types of environmental, social and other exposures",cite("9–11"),". Moreover, increasing attention is given to robustness analyses, where large-scale assessments can be examined for their sensitivity to analytical choices",cite("12,13"),". Here, we combined these two principles to assess the footprint of diverse county-level features on COVID-19 excess deaths across US counties in 2020–2024."]),
      body("Instead of pre-selecting predictors, we screened an exhaustive set of 2,745 county-level variables."),
      P(["Moreover, given that COVID-19 epidemiological estimates are known to be sensitive to the underlying data and modelling assumptions",cite("14"),", we examined the robustness of the results considering different sets of variables collected until just prior to the pandemic (2019), during the pandemic, or 5 or more years before the pandemic. Our analyses aimed to identify clusters and super-clusters of variables; examine how many of them have at least moderate correlations with excess deaths; and characterize whether some types of factors were more strongly related to excess deaths than others. Furthermore, we could assess whether the socioeconomic signature of excess deaths changed over time during the pandemic."]),

      // ===== METHODS =====
      H1("METHODS"),
      H2("County-level variables"),
      P(["County-level variables were drawn from the raw Area Health Resources File (AHRF)",cite("15")," (in contrast to pre-built composite area-level indices such as the Area Deprivation Index",cite("16"),"), downloaded from the Health Resources and Services Administration data warehouse (https://data.hrsa.gov/data/download?data=AHRF). The released file contains 7,236 county variable columns with different columns for the same variable measured at different years. Each variable carries an 8-character feature code (f + 7 digits) whose last two digits encode the data year (e.g. ‘10 = 2010, ‘18 = 2018, ‘22 = 2022). We applied a latest-year retention rule — for each base variable appearing in several years, only the most recent eligible year was kept up to and including 2019, so as to consider the most recent pre-pandemic information, leaving 3,162 assembled columns (the only exceptions are 11 county geographic-identifier codes and names — Core-Based / Combined Statistical Area and Metropolitan Division labels — that carry a 2020 Census vintage; these are administrative identifiers, not predictors, and several are among the zero-variance variables dropped below). Of these, 2,745 were AHRF predictor variables that form the input to all downstream analysis; the other 417 columns are not predictor variables — they were the mortality outcomes themselves (n=324), their population and death denominators (n=54), and geographic/administrative identifiers (n=39) (Supplementary Text; full list in Excluded_columns_417.tsv). Figure S1 diagrams the full pipeline from source files to this variable set."]),
      P(["In two sensitivity analyses, we also considered the most recent year available for each variable (up to 2023); and the most recent year up to 2015. Table S6 gives the per-data-year variable counts for the main and sensitivity analyses."]),
      H2("Normalization (per-capita)"),
      P(["All variables were expressed per capita. 203 variables were already rates, percentages, or ratios per population (thus per capita), while the remaining 2,401 were raw counts and were thus divided by the population in the respective year. Once all variables had been expressed per capita, they were rescaled across counties to a 0–9,999 range (9,999 representing the per-capita maximum). All correlations below were computed on the normalized data. Using a single fixed denominator (2019 county population) for every variable instead of each variable's own-year population left the screen essentially unchanged (16.5% versus 17.3% of variables reaching |CC| > 0.30, with the same leading correlates), confirming the result is insensitive to the per-capita denominator year."]),
      H2("Mortality outcome"),
      P(["The outcome was the per-year, age-standardized excess-death percentage (asedx_p) for each pandemic year 2020–2024, asedx_p = (ased / ased_bl) − 1, where ased is the county’s age-standardized observed deaths in the year and ased_bl is its pre-pandemic age-standardized expected baseline derived from the average of the three pre-pandemic years 2017–2019. It is a proportion (e.g. 0.20 = 20% above baseline); counties with a zero baseline yield an undefined value and are set to missing. Values were taken from a purpose-built county-level mortality database derived from the US Centers for Disease Control and Prevention WONDER underlying-cause-of-death data",cite("17"),"; suppressed small county counts (1–9 deaths) were recovered by a difference method (national totals less the target county subtracted from overall national totals). Because the outcome was age-standardized, differences between counties in age structure are already removed from it, so we do not include any age variable as a predictor. The main analysis uses the all-age series; the same outcome is also computed for the under-65 (LT65) and 65-and-over (GE65) age groups, which we analyze separately (Table S5)."]),
      H2("Association measure and effect-size bands"),
      P(["For each (variable, year) we computed a weighted Pearson correlation coefficient (CC) between the variable and the excess-death measure across counties, under population weighting (each county was weighted by its 2019 population). In sensitivity analyses, we also examined weighting by the 3/4 power and the square root of the population. We classified correlations based on their absolute value as weak (0–0.30), moderate (0.30–0.45), and strong (>0.45). We preferred focusing on the size of the correlation rather than the statistical significance, because given the large sample sizes involved p-values were expected to be highly significant even for what might be very weak correlations."]),
      H2("Semantic clustering of variables"),
      P(["Variable names were embedded with a sentence-transformer neural language model (MPNet)",cite("18,19")," and clustered using Ward’s agglomerative hierarchical clustering (Ward linkage)",cite("20"),". A key step is name cleaning: before embedding we strip surface tokens that carry no subject information — age bands (_35_44), sex, patient-care/role suffixes, and Population_ / #_ / %_ / Hospital_with_ prefixes — so the embedding keyed on what is measured rather than incidental wording. For example, the six age-banded pulmonary-disease physician counts in the dataset (Pulmonary_Diseases_<35, _35_44, _45_54, _55_64, _65_74, _75+) and the eighteen psychiatry variants spanning age bands and practice roles (Psychiatry_Total, Psychiatry_Patient_Care_Office_Based, Psychiatry_Patient_Care_Hospital_Full_Time_Staff, Psychiatry_35_44, …) each collapse to a single embedded subject (“Pulmonary diseases”, “Psychiatry”), and a per-capita rate such as %_Males_40_64_without_Health_Insurance enters as “Males 40–64 without health insurance”; they therefore group by what is measured rather than by the shared “_Patient_Care”, age-band, or “%_” wording. This roughly doubled cluster cohesion: the silhouette coefficient — a cluster-cohesion score from −1 to 1, higher meaning tighter, better-separated clusters",cite("21")," — rose above k=100 from ~0.20 to ~0.39. We selected k = 120 clusters and then generated 11 super-clusters. The organizing unit for the presented analysis is the 11 super-clusters; the 120-cluster level is a finer index used for de-duplication and within-cluster ranking, retained for reference but not load-bearing for the mortality findings."]),
      H2("Super-clusters"),
      body("To generate the 11 super-clusters, the 120 cluster labels were themselves embedded, and a Ward linkage on the label cosine distance was cut at k = 11 to give contiguous super-clusters (renumbered top-to-bottom in dendrogram order). The 11 super-cluster names were written to match each branch’s membership."),
      H2("Reproducibility"),
      body("The entire CC-dependent analysis layer regenerates from one script, code/run_standard_k120_w1.0.sh (steps A–K), writing all figures to figures_2745/ and tables to the project root and ward_sem_clean2_k120/. The k=120 clustering build, the 120 cluster labels, and the 11 super-cluster names are curated artifacts reused by the pipeline; everything downstream is scripted."),
      H2("Software"),
      body("All analyses were implemented in Python. Scripts were developed iteratively with the assistance of a large language model (Claude, Anthropic) used as coding aid: the investigators specified each analytical requirement, reviewed all generated code for correctness, and validated the outputs through multiple independent cross-checks, confirming that the |CC| moderate-association classification was stable across the 2015/2019/2022 data vintages and that the age-standardized excess-death outcome reproduced the source CDC WONDER mortality totals. Variable-name embedding used the MPNet sentence-transformer; clustering used scikit-learn. The final scripts are deterministic and reproducible and are provided, together with the key data, in the public repository (see Data and code availability)."),

      // ===== RESULTS (merged §3 + §4) =====
      H1("RESULTS"),
      H2("Structure of the variable space"),
      body("Cleaned-name clustering produced 120 cohesive semantic clusters (silhouette 0.42 at k=120; cluster sizes range 7–66 variables, median 18 — Figure S2). These clusters aggregated into 11 super-clusters (Table S1; Figure 1); the full membership (each super-cluster and its constituent cluster names) is given in Table S3."),
      body("Of the 2,745 screened variables, 2,727 carried a valid CC and a semantic-cluster assignment (the basis for Table 1); the remaining 18 were constant across all counties — all-zero counts of rare physician sub-specialties or services, or administrative name fields — giving zero variance and hence an undefined (uncomputable) correlation. Across these, the distribution of the maximum |CC| for any year in the period 2020–2024 has a median of 0.156, mean 0.181, 90th percentile 0.352, 95th percentile 0.406, and maximum 0.543. Overall, 17.3% of variables (472) reached the moderate correlation level (|CC| > 0.30) in at least one year and 2.8% (77) reached the strong correlation level (|CC| > 0.45) in at least one year. Figure 2 shows the full per-variable CC distributions by year and age group. As shown, moderate and strong correlations (|CC| > 0.30) appeared among variables in 2020 (9.1%) and 2021 (8.5%). In 2022 only some moderate correlations were seen (1.8%) and in 2023 essentially none (a single variable, 0.0%), while very few appeared in 2024 (1.3%). In the age strata, the patterns were very similar to the overall analysis, with moderate and strong correlations appearing in the first two years of the pandemic and then diminishing or even disappearing (even more prominently in the <65 years old stratum) in subsequent years."),
      body("For interpretation we group the eleven super-clusters by subject matter into two families: socioeconomic/demographic (SC1, SC2, SC3, SC5, SC8) and health-system (SC4, SC6, SC7, SC9, SC10, SC11). This grouping is by content, not a data-driven partition — a two-way cut of the cluster-label dendrogram would instead split the super-clusters into SC1–5 and SC6–11 (placing the physician-count super-cluster SC4 with the demographic block and employment SC8 with the workforce block)."),

      H2("Socioeconomic and demographic factors"),
      body("The variables with moderate or strong correlation were predominantly found in the demographic and socioeconomic family (Table 1). These five super-clusters — SC1 (Race, Ethnicity and Population by Age), SC2 (Geography, Environment and Housing), SC3 (Socioeconomic, Insurance and Demographic Characteristics), SC5 (Poverty, Insurance Coverage and Public Programs) and SC8 (Commuting and Industry Employment) — comprise 1,186 variables, 31% of which reach |CC| > 0.30; they account for 285 of the 395 variables in the moderate band and all 77 variables reaching the strong band."),
      body("The strongest correlations attained were with college attainment (CC −0.54 in 2021), uninsurance among adults 40–64 (+0.53 in 2021), and high income (−0.53 in 2021) in the overall analysis. In the ≥65 stratum the three strongest were all college-attainment measures (−0.50, −0.50 and −0.49, all in 2021); in the <65 stratum they were high household income (−0.50), the White non-Hispanic population aged 45–54 (−0.50), and college attainment (+0.50), with uninsurance among working-age adults just below (+0.50). The top six distinct moderately associated variables in each super-cluster (deduplicated to one per semantic cluster) are listed in Table S4, and the highest-|CC| variable in every one of the 120 clusters is given in the full per-cluster table (Top_metric_per_cluster_2020_2024_w1.0.tsv, provided as Supplementary Data)."),
      body("The pattern was internally consistent: affluence, education, and insurance were protective; poverty, uninsurance, disability, non-employment, and certain minority-population shares carried risk. Given that no single variable exceeded |CC| ≈ 0.54, no county characteristic explained more than ~29% of cross-county variance on its own (Figure S3)."),

      H2("Health-system factors"),
      body("Across the 1,541 health-system variables — the majority of the catalog (super-clusters 4, 6, 7, 9, 10, 11: physician counts, the physician workforce, and hospital capacity and facilities) — only 7.1% reached |CC| > 0.30 (with hospital-capacity and telehealth/imaging variables at 0–2%) and none reached a strong correlation, versus 31% of the 1,186 socioeconomic and demographic variables (super-clusters 1, 2, 3, 5, 8) (Table 1). These six health-system super-clusters contribute the bulk of the catalog (75 of 120 clusters) but little of the top signal. Physician-density variables correlate negatively with mortality but most of these correlations are weak. This is consistent with health-system workforce supply tracking the same affluence/urbanicity gradient that drives the demographic signal, rather than an independent protective effect."),

      H2("Robustness in sensitivity analyses using different variable years"),
      body("Each vintage is normalized on its own-year county population, exactly as in the main analysis. Variables were matched across vintages by base code (the f-code minus its last two year digits): 2,396 base-matched between the main analysis and the older-data sensitivity analysis (latest year ≤ 2015) and 2,754 between the main analysis and the more-recent-data (2023–2024) sensitivity analysis (the AHRF 2023–2024 release; predictor years ≈ 2022). Many matched variables are, however, identical by construction — their in-use vintage already qualifies, so the backward cutoff or the forward value-swap leaves them unchanged — and such variables are uninformative for a robustness test; we therefore restrict the comparison to the variables whose value actually changed between releases (1,617 for the ≤2015 comparison and 1,971 for the 2023–2024 comparison; the 779 and 783 unchanged variables are excluded). Among these changed variables the per-variable correlation with excess death is highly stable: each variable’s signed CC at its strongest year (2020–2024) in the main analysis tracks the older-data value at Spearman ρ = 0.97 (Pearson 0.97) and the more-recent-data value at ρ = 0.91 (Pearson 0.93); the moderate-association (|CC| > 0.30) classification agrees 98.3% and 94.6% (Table S2); and among the ~293 changed variables reaching |CC| > 0.30 in the main analysis, none reverse sign with the older data and only two do with the more recent data (Figure S6). Full distributions of correlations appear in Figure S4 and Figure S5."),

      H2("Sensitivity analysis on population weighting"),
      P(["To assess sensitivity to the weighting choice, we recomputed all correlations across a range of weight powers (each county weighted by its 2019 population raised to the power p; Table S7). The identity and ranking of the top correlates were unchanged throughout — uninsurance among adults 40–64 and college attainment remained the strongest — but the magnitudes scaled smoothly with p. At p = 0.75, a middle ground that roughly halves the dominance of the largest counties (Kish effective sample size",cite("22")," 712, versus 282 at full weighting), 10.6% of variables reached a max |CC| > 0.30 and 1.0% the strong band, versus 17.3% and 2.8% under the primary full-population weighting; the single strongest correlation was 0.49 versus 0.54. Square-root weighting (p = 0.5) brought the signal down to roughly the unweighted level (4.3% moderate, none strong). The headline effect sizes are therefore sensitive to how strongly large metropolitan counties are weighted, although the qualitative pattern — socioeconomic and demographic variables dominating, health-system variables weak — holds at every weighting."]),
      // ===== DISCUSSION =====
      H1("DISCUSSION"),
      P(["We have evaluated, on a large scale, the correlational footprint of 2,745 county-level variables against excess deaths during 2020–2024. Besides demographics, the social-determinant gradient that predicts many adverse health outcomes — education",cite("23"),", income",cite("24"),", and insurance",cite("25")," being protective and poverty, uninsurance, disability, non-employment, and specific minority-population shares being risk-associated — offered the strongest signals for associations with excess deaths during the pandemic years. Health-system supply and related variables",cite("26")," added a weak, mostly protective and likely confounded signal. Overall, even the strongest single variable topped out at |CC| ≈ 0.54; therefore, no county characteristic is close to deterministic, and the most honest summary may be the full-scale presentation of a multifactor socioeconomic gradient rather than any one specific driver."]),
      P(["A standing critique of ecological COVID studies is that associations are fragile to data choices. This problem largely jeopardizes studies that claim to identify highly specific predictors as being more important. However, in our analysis, the big picture where thousands of variables are considered remained robust to different analytical choices. Moreover, we demonstrated that results did not change substantially when we considered earlier or later measurements for the variables. This may reflect the fact that most of the county-level features do not change substantially over time. Disadvantaged counties remain disadvantaged and affluent ones remain affluent, with relatively few exceptions. Socioeconomic factors remain pervasive determinants of health and disease outcomes."]),
      P(["We also found that the strength of the observed correlations largely tracked the magnitude of excess death itself. Excess-death measures were strongest in 2020–21, decaying gradually with aggregate excess mortality returning to approximately zero by 2023–2024. This socioeconomic disadvantage was most important in the early phase of the pandemic, before vaccines were available and before the emergence of less lethal Omicron variants",cite("27"),". The weaker correlations seen with health-system factors may suggest that socioeconomic disadvantage may be more important than the exact capacity, resources and specialization of the health system. People who are uninsured and lack access, and those who suffer from marginalization, may not be able to benefit much from improvements in the health system at the hospital level and workforce. Socioeconomic factors operate at a deeper root than can be fixed by traditional hospital care. We should acknowledge, however, that the health-system variables that we used reflected the baseline structural endowment rather than real-time surge or ICU strain."]),
      P(["The clustering approach that we used offered some advantages in dealing with the very wide space of almost 3,000 variables. The super-clusters further allowed a more facile naming of the organized patterns of variables and high-level comparisons of different types of factors. However, it does have some limitations. A few variables may have been imperfectly placed, and the k = 120 and k = 11 choices were analyst decisions, but they were justified by silhouette metrics and dendrogram structure."]),
      P(["The main limitation of this analysis is its ecological nature. Due to potential ecological fallacy",cite("28"),", individual-level inferences should be avoided and causation claims with specific factors would be precarious. We argue, nevertheless, that once this is fully acknowledged, obtaining such a bird's-eye picture may be preferable to trying to de-confound in vain thousands of highly correlated and confounded factors. We should also acknowledge that reverse causality is also possible, especially in the sensitivity analysis that used county-level variables obtained during the pandemic years. Moreover, we did not use statistical significance testing, as this would have yielded a huge number of nominally significant results of questionable meaning. The magnitude of the correlations is more meaningful. Their exact magnitude nevertheless depends on the nature of the population weighting."]),

      // ===== REFERENCES =====
      H1("REFERENCES"),
      ...REFERENCES,

      // ===== MAIN TABLES =====
      H1("TABLES"),
      caption("Table 1","Super-cluster association summary. For each of the 11 super-clusters, the count of variables whose maximum |CC| across the all-age years 2020–2024 (population-weighted, NORMED) reaches the moderate band (0.30 < |CC| < 0.45) and the strong band (|CC| > 0.45), with the percentage attaining |CC| > 0.30 and the mean of per-variable maximum |CC| (2,727 variables with a valid CC and a semantic-cluster assignment). Sorted by % |CC| > 0.30, descending. Socioeconomic and demographic super-clusters lead; the surgical/specialist physician workforce, hospital capacity, and hospital telehealth/imaging show essentially no moderate correlation with pandemic excess death. The last two columns give the single strongest (highest-|CC|) variable in each super-cluster and its signed CC at the year of maximum |CC| (a positive CC marks higher excess mortality)."),
      TABLE_SCSIG,

      // ===== MAIN FIGURES =====
      H1("FIGURES"),
      ...figure("sc_label_heatmap_sig_w1.0.png",{w:624,h:329},"Figure 1",
        "120×120 cluster-label cosine matrix with per-super-cluster-coloured Ward dendrogram (symlog cosine-distance axis). Cluster labels are reddened when a cluster holds ≥3 variables each reaching the moderate band (|CC| > 0.30) in ≥2 years."),
      new Paragraph({children:[new PageBreak()]}),
      ...figureAt(ROOT+"/full_w1.0/cc_histograms_T_ccband.png",{w:612,h:360},"Figure 2",
        "Per-variable correlation-coefficient (CC) distributions, 2019-vintage predictors, population-weighted. Columns: death years 2020–2024 plus pooled 2020–2023; rows: All / Ages ≥65 / Ages <65. log₁₀ count on the y-axis; dark blue marks moderate (|CC| > 0.30), orange strong (|CC| > 0.45); red line at CC = 0. Almost all mass is near zero."),

      new Paragraph({children:[new PageBreak()]}),

      // ===== SUPPLEMENT =====
      H1("SUPPLEMENT"),
      H2("Supplementary Text"),
      body("Significance mode. A p-value / log-probability (LP) mode exists in the pipeline but is dormant; the project default throughout this paper is the fixed |CC| effect-size rule (moderate |CC| > 0.30; strong |CC| > 0.45), a magnitude threshold rather than a statistical-significance test."),
      body("Excluded columns. Assembly retains 3,162 columns, of which 2,745 are AHRF predictor variables with a plain-English description — the input to all analysis. The remaining 417 columns are not predictor variables and were never candidates for the semantic or correlation analysis: 324 are the mortality / excess-death outcome series themselves (asedx_p and the analogous ASMR, CMR and life-expectancy measures, across years and age bands), 54 are the population and death denominators used to construct those outcomes, and 39 are geographic / administrative identifiers (FIPS and entity codes, CBSA and region codes, land area, and urban/rural population, housing and block tallies). No AHRF predictor variable was dropped for lacking a description. The full list of all 417 is provided as Supplementary Data (Excluded_columns_417.tsv)."),
      H2("Supplementary Data"),
      body("Seven machine-readable files accompany the manuscript: Top_metric_per_cluster_2020_2024_w1.0.tsv (the highest-|CC| variable in every one of the 120 clusters, 2020–2024 — the per-cluster source for the Table S4 representatives; a Supplementary Data file, not itself a numbered table); Table_S3_supercluster_cluster_names.tsv (the full super-cluster → cluster membership listing, also rendered as Table S3 below); Table_S4_top6_metrics_per_supercluster.tsv (the top six distinct moderately associated variables per super-cluster, rendered as Table S4); Table_S4A_collapsed_variants.tsv (every near-duplicate variable removed in the Table S4 deduplication, listed under its representative); Table_S5_age_band_divergence.tsv (moderate-association counts and max |CC| by year and age band, rendered as Table S5); Table_S6_vintage_composition.tsv (variable counts by data-year for each AHRF release, rendered as Table S6); and Excluded_columns_417.tsv (the 417 non-predictor columns excluded from analysis)."),
      H2("Supplementary Tables"),
      caption("Table S1","The 11 super-clusters (Ward cut, k=11) and their size. Sizes count the 2,727 variables with a valid correlation (the 18 of the 2,745 screened variables that lacked a usable cross-county correlation are omitted), matching the basis of Table 1."),
      TABLE1,
      caption("Table S2","Cross-vintage agreement on moderate-association status (|CC| > 0.30), restricted to the variables whose vintage value actually changed (779 backward and 783 forward base-matched variables that are identical by construction — not rolled back or not changed — are excluded as uninformative). The 2015 comparison is a retrospective cutoff of the 2019–2020 release, not an independent download; agreement is still partly carried by concordant sub-threshold variables."),
      TABLE3,
      caption("Table S3","The 11 super-clusters and their constituent 120 semantic clusters (cluster labels)."),
      TABLE_S6,
      new Paragraph({children:[new PageBreak()]}),
      caption("Table S4","Top six moderately associated (|CC| > 0.30) distinct variables per super-cluster, with the signed CC at the year of maximum |CC| (Yr). Deduplicated: within each super-cluster only one representative — the highest-|CC| member — is shown per k=120 semantic cluster, so the listed variables are distinct measures rather than age/sex/race/vintage variants of the same one. The Collapsed column gives the number of other moderately associated variables in that cluster that the representative stands for; those variants are enumerated in Table_S4A_collapsed_variants.tsv (Supplementary Data). Where a super-cluster has fewer than six such clusters, fewer than six rows appear. Same basis and super-cluster ordering as Table 1; SC10 (Hospital Telehealth and Advanced Imaging Services) has no variable reaching |CC| > 0.30. Variable names are AHRF descriptions (verbatim, including source spellings)."),
      TABLE_S7,
      caption("Table S5","Age-band divergence over the pandemic. Counts of moderately associated variables (|CC| > 0.30, strict) and the single strongest |CC| for the all-age, under-65 (LT65) and 65-and-over (GE65) excess-death outcomes, by year (population-weighted, 2019-vintage predictors). The under-65 signal is confined to 2020–2021; the ≥65 signal persists and re-strengthens through 2024. (A displayed max of 0.30 for all-age 2023 is rounding — no variable strictly exceeds 0.30, hence zero in that band.)"),
      TABLE_S8,
      caption("Table S6","Data-year composition of the variables actually used in each analysis, after the latest-year retention rule (one most-recent year retained per variable). Columns: the ≤2015 backward-cutoff vintage, the ≤2019 main analysis, and the 2023–2024 forward vintage; each row gives the number of retained variables carrying that data year (f-coded predictors plus the non-f-code count, rate and land-area predictors; pure geographic/administrative identifier codes are excluded). The ≤2019 column is dominated by 2010, 2014 and 2018 vintages; the 2023–2024 column by 2022. Totals 2,395 / 2,754 / 2,754."),
      TABLE_S9,
      caption("Table S7","Sensitivity of the variable–death correlations to the county weighting scheme. Each county is weighted by its 2019 population raised to the power p (p = 0 unweighted; p = 1.0 the primary full-population analysis). For each scheme: the Kish effective sample size; the percentage of the 2,727 analysed variables whose maximum |CC| over 2020–2024 reaches the moderate (> 0.30) and strong (> 0.45) bands; the median of that maximum |CC|; and the single largest |CC|. The identity and ranking of the top correlates (uninsurance among adults 40–64; college attainment) are unchanged across schemes — only the magnitudes scale with p. The unweighted row is sensitive to the inclusion of very small, noisy counties (applying a legacy minimum-population floor raises the unweighted moderate fraction to ~3.6%)."),
      TABLE_WEIGHT,

      H2("Supplementary Figures"),
      ...figureAt(ROOT+"/Supplementary_Tables_Figures/Fig_S1.png",{w:612,h:344},"Figure S1",
        "Pipeline overview, from source files (AHRF technical documentation, AHRF data, CDC WONDER mortality) to the analysis variable set and master data table. Documents the reduction from 7,236 raw AHRF variable columns (all vintages) to the 2,745 described variables used downstream."),
      new Paragraph({children:[new PageBreak()]}),
      ...figureAt(ROOT+"/Supplementary_Tables_Figures/cluster_size_histogram.png",{w:600,h:297},"Figure S2",
        "Distribution of variable counts across the 120 semantic clusters (sizes 7–66 variables, median 18)."),
      new Paragraph({children:[new PageBreak()]}),
      ...figure("sem120_rep_absCC_heatmap_w1.0_cap0.45.png",{w:560,h:405},"Figure S3",
        "120×120 representative-variable |CC| heatmap (each cluster’s highest-|CC| member); cell shading is |CC| magnitude (white→red, capped at 0.45). A cluster label is printed in red when its representative variable reaches |CC| > 0.30 (i.e. the cluster’s strongest variable is moderately associated) — a looser criterion than Figure 1, which reddens a cluster only when ≥3 of its variables reach the moderate band in ≥2 years. The bright blocks are the demographic and socioeconomic super-clusters."),
      new Paragraph({children:[new PageBreak()]}),
      ...figureAt(ROOT+"/Supplementary_Tables_Figures/cc_histograms_T_2015.png",{w:612,h:360},"Figure S4",
        "Variable–death CC distributions for the 2015 backward-cutoff vintage (population-weighted). Columns: death years 2020–2024 plus pooled 2020–2023; rows: All / Ages ≥65 / Ages <65. log₁₀ count on the y-axis; dark blue = moderate (|CC| > 0.30), orange = strong (|CC| > 0.45); red line at CC = 0."),
      new Paragraph({children:[new PageBreak()]}),
      ...figureAt(ROOT+"/Supplementary_Tables_Figures/cc_histograms_T_2022.png",{w:612,h:360},"Figure S5",
        "Variable–death CC distributions for the 2022 forward (AHRF 2023–2024) vintage, same axes and coloring as Figure S4. The moderate and strong tails are populated comparably to Figure S4 (2015) and to the 2019 standard run — the visual counterpart of the high variable-level vintage agreement (Table S2; Figure S6)."),
      new Paragraph({children:[new PageBreak()]}),
      ...figureAt(ROOT+"/Supplementary_Tables_Figures/cc_vintage_scatter.png",{w:640,h:314},"Figure S6",
        "Cross-vintage stability of the per-variable correlation with excess death. The comparison is restricted to the variables whose vintage value actually changed between releases: variables that are identical by construction — not rolled back (≤2015) or not changed (2023–2024) — are excluded as uninformative (779 excluded backward, leaving 1,617 tested; 783 excluded forward, leaving 1,971 tested). Each plotted point is one such variable; the axes are its signed correlation coefficient (the per-variable maximum |CC| over 2020–2024, with sign) in the main (2019) analysis (x) versus the backward (latest year ≤ 2015; left panel) and forward (AHRF 2023–2024 release, predictor years ≈ 2022; right panel) sensitivity analyses (y). The dashed line is identity; dotted lines mark |CC| = 0.30. Points are red where the sign disagrees between vintages; among the variables reaching |CC| > 0.30 in the main analysis none reverse sign backward and only two do forward. Each panel annotates the Pearson and Spearman coefficients, the number of changed variables tested, and the number of identical-by-construction variables excluded."),
    ]
  }]
});

Packer.toBuffer(doc).then(buf=>{fs.writeFileSync(OUT,buf);console.log("WROTE "+OUT+" ("+buf.length+" bytes)");});
