# 🔬 学术期刊 & 预印本 RSS 链接汇总
---

## 📐 RSS URL 构造规则速查

| 出版商 | URL 模式 | 示例 |
|--------|---------|------|
| **Nature** | `https://www.nature.com/{CODE}.rss` | `nature.com/nature.rss` |
| **Nature (旧版feed)** | `https://feeds.nature.com/{CODE}/rss/current` | `feeds.nature.com/nchem/rss/current` |
| **Science** | `https://www.science.org/action/showFeed?type=etoc&feed=rss&jc={CODE}` | `jc=science` |
| **ACS** | `https://pubs.acs.org/action/showFeed?type=etoc&feed=rss&jc={CODE}` | `jc=jacsat` |
| **ACS (旧版)** | `https://pubs.acs.org/wls/alerts/rss/{CODE}.rss` | `jacsat.rss` |
| **RSC** | `https://feeds.rsc.org/rss/{CODE}` | `rss/sc` (Chemical Science) |
| **Wiley** | `https://onlinelibrary.wiley.com/rss/journal/{ISSN}` | `journal/1521-3773` |
| **Elsevier** | `https://rss.sciencedirect.com/publication/science/{ISSN}` | `science/00404020` |
| **APS** | `https://feeds.aps.org/rss/recent/{CODE}.xml` | `prl.xml` |
| **Cell Press** | `https://www.cell.com/{JOURNAL}/current.rss` | `cell/current.rss` |
| **PNAS** | `https://www.pnas.org/action/showFeed?type=etoc&feed=rss` | — |
| **Thieme** | `https://www.thieme-connect.com/rss/thieme/en/{JOURNAL}.xml` | `synlett.xml` |
| **Springer** | `https://link.springer.com/search.rss?search-within=Journal&facet-journal-id={ID}` | `id=10994` |
| **IEEE** | `https://ieeexplore.ieee.org/rss/TOC{JOURNAL_NO}.XML` | — |
| **arXiv** | `https://rss.arxiv.org/rss/{CATEGORY}` | `rss/cs.AI` |
| **bioRxiv** | `https://connect.biorxiv.org/biorxiv_xml.php?subject={CATEGORY}` | `subject=biochemistry` |
| **medRxiv** | `https://connect.medrxiv.org/medrxiv_xml.php?subject={CATEGORY}` | `subject=epidemiology` |

---

## 一、Nature 系列

### 旗舰刊
| 期刊 | RSS URL | 状态 |
|------|---------|------|
| Nature | `https://www.nature.com/nature.rss` | ✅ |
| Nature (旧版) | `https://feeds.nature.com/nature/rss/current` | ✅ |

### 子刊精选
| 期刊 | RSS URL | 状态 |
|------|---------|------|
| Nature Chemistry | `https://www.nature.com/nchem.rss` | ✅ |
| Nature Materials | `https://www.nature.com/nmat.rss` | ✅ |
| Nature Nanotechnology | `https://www.nature.com/nnano.rss` | ✅ |
| Nature Catalysis | `https://www.nature.com/natcatal.rss` | ✅ |
| Nature Communications | `https://www.nature.com/ncomms.rss` | ✅ |
| Nature Physics | `https://www.nature.com/nphys.rss` | ✅ |
| Nature Photonics | `https://www.nature.com/nphoton.rss` | ✅ |
| Nature Energy | `https://www.nature.com/nenergy.rss` | ✅ |
| Nature Sustainability | `https://www.nature.com/natsustain.rss` | ✅ |
| Nature Methods | `https://www.nature.com/nmeth.rss` | ✅ |
| Nature Biotechnology | `https://www.nature.com/nbt.rss` | ✅ |
| Nature Biomedical Engineering | `https://www.nature.com/natbiomedeng.rss` | ✅ |
| Nature Electronics | `https://www.nature.com/natelectron.rss` | ✅ |
| Nature Machine Intelligence | `https://www.nature.com/natmachintell.rss` | ✅ |
| Nature Computational Science | `https://www.nature.com/natcomputsci.rss` | ✅ |
| Nature Reviews Chemistry | `https://www.nature.com/natrevchem.rss` | ✅ |
| Nature Reviews Materials | `https://www.nature.com/natrevmats.rss` | ✅ |
| Nature Synthesis | `https://www.nature.com/natsynth.rss` | ✅ |
| Nature Water | `https://www.nature.com/natwater.rss` | ✅ |
| Nature Chemical Engineering | `https://www.nature.com/natchemeng.rss` | ✅ |
| Nature Chemical Biology | `https://www.nature.com/nchembio.rss` | ✅ |
| Scientific Reports | `https://www.nature.com/srep.rss` | ✅ |
| Scientific Data | `https://www.nature.com/sdata.rss` | ✅ |
| Communications Chemistry | `https://www.nature.com/commschem.rss` | ✅ |
| Communications Materials | `https://www.nature.com/commsmat.rss` | ✅ |

### 生命科学
| 期刊 | RSS URL | 状态 |
|------|---------|------|
| Nature Medicine | `https://www.nature.com/nm.rss` | ✅ |
| Nature Immunology | `https://www.nature.com/ni.rss` | ✅ |
| Nature Cell Biology | `https://www.nature.com/ncb.rss` | ✅ |
| Nature Structural & Molecular Biology | `https://www.nature.com/nsmb.rss` | ✅ |
| Nature Reviews Molecular Cell Biology | `https://www.nature.com/nrm.rss` | ✅ |
| Nature Reviews Immunology | `https://www.nature.com/nri.rss` | ✅ |
| Nature Reviews Microbiology | `https://www.nature.com/nrmicro.rss` | ✅ |
| Nature Reviews Drug Discovery | `https://www.nature.com/nrd.rss` | ✅ |
| Nature Protocols | `https://www.nature.com/nprot.rss` | ✅ |

> 💡 **Nature 通用规则**：任意 Nature 子刊的 RSS = `https://www.nature.com/{期刊简写}.rss`

---

## 二、Science 系列

| 期刊 | RSS URL | 状态 |
|------|---------|------|
| Science | `https://www.science.org/action/showFeed?type=etoc&feed=rss&jc=science` | ✅ |
| Science Advances | `https://www.science.org/action/showFeed?type=etoc&feed=rss&jc=sciadv` | ✅ |
| Science Immunology | `https://www.science.org/action/showFeed?type=etoc&feed=rss&jc=sciimmunol` | ✅ |
| Science Translational Medicine | `https://www.science.org/action/showFeed?type=etoc&feed=rss&jc=stm` | ✅ |
| Science Robotics | `https://www.science.org/action/showFeed?type=etoc&feed=rss&jc=scirobotics` | ✅ |
| Science Signaling | `https://www.science.org/action/showFeed?type=etoc&feed=rss&jc=signaling` | ✅ |

> 💡 Science 旧版：`http://science.sciencemag.org/rss/current.xml`

---

## 三、ACS 系列

### 🧪 化学综合与核心期刊
| 期刊 | 简写 | RSS URL | 状态 |
|------|------|---------|------|
| J. Am. Chem. Soc. | `jacsat` | `https://pubs.acs.org/action/showFeed?type=etoc&feed=rss&jc=jacsat` | ✅ |
| Chemical Reviews | `chreay` | `https://pubs.acs.org/action/showFeed?type=etoc&feed=rss&jc=chreay` | ✅ |
| Accounts of Chemical Research | `achre4` | `https://pubs.acs.org/action/showFeed?type=etoc&feed=rss&jc=achre4` | ✅ |
| Accounts of Materials Research | `accmaterres` | `https://pubs.acs.org/rss/accmaterres` | ✅ |
| ACS Central Science | `acscii` | `https://pubs.acs.org/action/showFeed?type=etoc&feed=rss&jc=acscii` | ✅ |
| Chemical & Biomedical Imaging | `cbimid` | `https://pubs.acs.org/rss/cbimid` | ✅ |
| Chemistry of Materials | `cmatex` | `https://pubs.acs.org/action/showFeed?type=etoc&feed=rss&jc=cmatex` | ✅ |
| C&EN Latest News | — | `https://cen.acs.org/rss/latest` | ✅ |

### 🌱 农业、食品与环境
| 期刊 | 简写 | RSS URL | 状态 |
|------|------|---------|------|
| J. Agricultural and Food Chemistry | `jafcau` | `https://pubs.acs.org/action/showFeed?type=etoc&feed=rss&jc=jafcau` | ✅ |
| ACS Agricultural Science & Technology | `agsct` | `https://pubs.acs.org/rss/agsct` | ✅ |
| ACS Food Science & Technology | `afsthl` | `https://pubs.acs.org/action/showFeed?type=etoc&feed=rss&jc=afsthl` | ✅ |
| ACS ES&T Air | `estair` | `https://pubs.acs.org/rss/estair` | ✅ |
| ACS ES&T Engineering | `estengg` | `https://pubs.acs.org/rss/estengg` | ✅ |
| ACS ES&T Toxicology | `esttox` | `https://pubs.acs.org/rss/esttox` | ✅ |
| ACS ES&T Water | `estwater` | `https://pubs.acs.org/rss/estwater` | ✅ |
| ACS Environmental Au | `acsenvironau` | `https://pubs.acs.org/rss/acsenvironau` | ✅ |
| Environmental Science & Technology | `esthag` | `https://pubs.acs.org/action/showFeed?type=etoc&feed=rss&jc=esthag` | ✅ |
| Environmental Science & Technology Letters | `estlett` | `https://pubs.acs.org/rss/estlett` | ✅ |
| Environmental Health Perspectives | — | `https://ehp.niehs.nih.gov/rss/` | ✅ |

### ⚡ 能源、应用与工程
| 期刊 | 简写 | RSS URL | 状态 |
|------|------|---------|------|
| ACS Applied Materials & Interfaces | `aamick` | `https://pubs.acs.org/action/showFeed?type=etoc&feed=rss&jc=aamick` | ✅ |
| ACS Applied Nano Materials | `acsanm` | `https://pubs.acs.org/rss/acsanm` | ✅ |
| ACS Applied Energy Materials | `acsaelm` | `https://pubs.acs.org/rss/acsaelm` | ✅ |
| ACS Applied Electronic Materials | `acsaelm` | `https://pubs.acs.org/rss/acsaelm` | ✅ |
| ACS Applied Catalysis | `acsapcat` | `https://pubs.acs.org/rss/acsapcat` | ✅ |
| ACS Applied Engineering Materials | `acsapem` | `https://pubs.acs.org/rss/acsapem` | ✅ |
| ACS Applied Polymer Materials | `acsapm` | `https://pubs.acs.org/rss/acsapm` | ✅ |
| ACS Engineering Au | `acsenau` | `https://pubs.acs.org/rss/acsenau` | ✅ |
| ACS Energy Letters | `aelccp` | `https://pubs.acs.org/action/showFeed?type=etoc&feed=rss&jc=aelccp` | ✅ |
| ACS Photonics | `acsphotonics` | `https://pubs.acs.org/rss/acsphotonics` | ✅ |
| ACS Sensors | `ascefj` | `https://pubs.acs.org/action/showFeed?type=etoc&feed=rss&jc=ascefj` | ✅ |
| ACS Sustainable Chemistry & Engineering | `ascecg` | `https://pubs.acs.org/action/showFeed?type=etoc&feed=rss&jc=ascecg` | ✅ |
| ACS Catalysis | `accacs` | `https://pubs.acs.org/action/showFeed?type=etoc&feed=rss&jc=accacs` | ✅ |
| ACS Materials Letters | `amlcef` | `https://pubs.acs.org/action/showFeed?type=etoc&feed=rss&jc=amlcef` | ✅ |
| ACS Nano | `ancac3` | `https://pubs.acs.org/action/showFeed?type=etoc&feed=rss&jc=ancac3` | ✅ |
| ACS Nano Medicine | `acsnanomed` | `https://pubs.acs.org/rss/acsnanomed` | ✅ |
| ACS Nanoscience Au | `acsnsau` | `https://pubs.acs.org/rss/acsnsau` | ✅ |
| Nano Letters | `nalefd` | `https://pubs.acs.org/action/showFeed?type=etoc&feed=rss&jc=nalefd` | ✅ |
| Crystal Growth & Design | `cgdefu` | `https://pubs.acs.org/action/showFeed?type=etoc&feed=rss&jc=cgdefu` | ✅ |
| Langmuir | `langd5` | `https://pubs.acs.org/action/showFeed?type=etoc&feed=rss&jc=langd5` | ✅ |
| Macromolecules | `mamobx` | `https://pubs.acs.org/action/showFeed?type=etoc&feed=rss&jc=mamobx` | ✅ |
| Industrial & Engineering Chemistry Research | `iecr` | `https://pubs.acs.org/rss/iecr` | ✅ |

### 🧬 生物、医药与健康
| 期刊 | 简写 | RSS URL | 状态 |
|------|------|---------|------|
| Biochemistry | `bichaw` | `https://pubs.acs.org/action/showFeed?type=etoc&feed=rss&jc=bichaw` | ✅ |
| Bioconjugate Chemistry | `bcches` | `https://pubs.acs.org/action/showFeed?type=etoc&feed=rss&jc=bcches` | ✅ |
| Biomacromolecules | `bomaf6` | `https://pubs.acs.org/action/showFeed?type=etoc&feed=rss&jc=bomaf6` | ✅ |
| ACS Bio & Med Chem Au | `acsbiomedchemau` | `https://pubs.acs.org/rss/acsbiomedchemau` | ✅ |
| ACS Biomaterials Science & Engineering | `acsbiomater` | `https://pubs.acs.org/rss/acsbiomater` | ✅ |
| ACS Chemical Biology | `acbcct` | `https://pubs.acs.org/action/showFeed?type=etoc&feed=rss&jc=acbcct` | ✅ |
| ACS Chemical Health & Safety | `chemsafety` | `https://pubs.acs.org/rss/chemsafety` | ✅ |
| ACS Chemical Neuroscience | `acncdm` | `https://pubs.acs.org/action/showFeed?type=etoc&feed=rss&jc=acncdm` | ✅ |
| ACS Earth and Space Chemistry | `acsesci` | `https://pubs.acs.org/rss/acsesci` | ✅ |
| ACS Infectious Diseases | `aidcbc` | `https://pubs.acs.org/action/showFeed?type=etoc&feed=rss&jc=aidcbc` | ✅ |
| ACS Medicinal Chemistry Letters | `amclct` | `https://pubs.acs.org/action/showFeed?type=etoc&feed=rss&jc=amclct` | ✅ |
| ACS Pharmacology & Translational Science | `acsptsci` | `https://pubs.acs.org/rss/acsptsci` | ✅ |
| ACS Synthetic Biology | `asbcd6` | `https://pubs.acs.org/action/showFeed?type=etoc&feed=rss&jc=asbcd6` | ✅ |
| Chemical Research in Toxicology | `crtoec` | `https://pubs.acs.org/action/showFeed?type=etoc&feed=rss&jc=crtoec` | ✅ |
| J. Medicinal Chemistry | `jmcmar` | `https://pubs.acs.org/action/showFeed?type=etoc&feed=rss&jc=jmcmar` | ✅ |
| J. Natural Products | `jnprdf` | `https://pubs.acs.org/action/showFeed?type=etoc&feed=rss&jc=jnprdf` | ✅ |
| J. Proteome Research | `jprobs` | `https://pubs.acs.org/action/showFeed?type=etoc&feed=rss&jc=jprobs` | ✅ |
| Molecular Pharmaceutics | `mpohbp` | `https://pubs.acs.org/action/showFeed?type=etoc&feed=rss&jc=mpohbp` | ✅ |
| Organic Letters | `orlef7` | `https://pubs.acs.org/action/showFeed?type=etoc&feed=rss&jc=orlef7` | ✅ |
| The Journal of Organic Chemistry | `joceah` | `https://pubs.acs.org/action/showFeed?type=etoc&feed=rss&jc=joceah` | ✅ |
| Organic Process Research & Development | `oprdfk` | `https://pubs.acs.org/action/showFeed?type=etoc&feed=rss&jc=oprdfk` | ✅ |

### ⚛️ 物理、理论与分析化学
| 期刊 | 简写 | RSS URL | 状态 |
|------|------|---------|------|
| Analytical Chemistry | `ancham` | `https://pubs.acs.org/action/showFeed?type=etoc&feed=rss&jc=ancham` | ✅ |
| ACS Measurement Science Au | `amachv` | `https://pubs.acs.org/action/showFeed?type=etoc&feed=rss&jc=amachv` | ✅ |
| Artificial Photosynthesis | `acsap` | `https://pubs.acs.org/rss/acsap` | ✅ |
| Chemical Physics Au | `acscpa` | `https://pubs.acs.org/rss/acscpa` | ✅ |
| Energy & Fuels | `enfuem` | `https://pubs.acs.org/action/showFeed?type=etoc&feed=rss&jc=enfuem` | ✅ |
| Inorganic Chemistry | `inocaj` | `https://pubs.acs.org/action/showFeed?type=etoc&feed=rss&jc=inocaj` | ✅ |
| Organometallics | `orgnd7` | `https://pubs.acs.org/action/showFeed?type=etoc&feed=rss&jc=orgnd7` | ✅ |
| J. Chemical & Engineering Data | `jced` | `https://pubs.acs.org/rss/jced` | ✅ |
| J. Chemical Education | `jchemeduc` | `https://pubs.acs.org/rss/jchemeduc` | ✅ |
| J. Chemical Information and Modeling | `jcisd8` | `https://pubs.acs.org/action/showFeed?type=etoc&feed=rss&jc=jcisd8` | ✅ |
| J. Chemical Theory and Computation | `jctcce` | `https://pubs.acs.org/action/showFeed?type=etoc&feed=rss&jc=jctcce` | ✅ |
| J. Physical Chemistry A | `jpcafh` | `https://pubs.acs.org/action/showFeed?type=etoc&feed=rss&jc=jpcafh` | ✅ |
| J. Physical Chemistry B | `jpcbfk` | `https://pubs.acs.org/action/showFeed?type=etoc&feed=rss&jc=jpcbfk` | ✅ |
| J. Physical Chemistry C | `jpccck` | `https://pubs.acs.org/action/showFeed?type=etoc&feed=rss&jc=jpccck` | ✅ |
| J. Physical Chemistry Letters | `jpclcd` | `https://pubs.acs.org/action/showFeed?type=etoc&feed=rss&jc=jpclcd` | ✅ |
| JACS Au | `jaaucr` | `https://pubs.acs.org/action/showFeed?type=etoc&feed=rss&jc=jaaucr` | ✅ |
| Photon Science | `acsps` | `https://pubs.acs.org/rss/acsps` | ✅ |
| Precision Chemistry | `precision` | `https://pubs.acs.org/rss/precision` | ✅ |

### 🧩 其他学科与新刊
| 期刊 | 简写 | RSS URL | 状态 |
|------|------|---------|------|
| ACS Materials Au | `acsmat` | `https://pubs.acs.org/rss/acsmat` | ✅ |
| ACS Omega | `acsomega` | `https://pubs.acs.org/rss/acsomega` | ✅ |
| ACS Organic & Inorganic Au | `acsorgau` | `https://pubs.acs.org/rss/acsorgau` | ✅ |
| ACS Physical Chemistry Au | `acsphysau` | `https://pubs.acs.org/rss/acsphysau` | ✅ |
| ACS Polymers Au | `acspsau` | `https://pubs.acs.org/rss/acspsau` | ✅ |
| ACS Sustainable Resource Management | `acsrm` | `https://pubs.acs.org/rss/acsrm` | ✅ |
| Chem & Bio Engineering | `cbie` | `https://pubs.acs.org/rss/cbie` | ✅ |
| Digital Medical Engineering | `dime` | `https://pubs.acs.org/rss/dime` | ✅ |
| Polymer Science & Technology | `acspt` | `https://pubs.acs.org/rss/acspt` | ✅ |

> 💡 **ACS 通用规则**：`https://pubs.acs.org/action/showFeed?type=etoc&feed=rss&jc={期刊简写}`  
> 新版格式（部分期刊支持）：`https://pubs.acs.org/rss/{简写}`  
> 旧版格式：`https://pubs.acs.org/wls/alerts/rss/{简写}.rss`  
> 完整 ACS 期刊简写列表见：https://pubs.acs.org/page/follow.html?widget=follow-pane-rss

---

## 四、RSC 系列

| 期刊 | Code | RSS URL | 状态 |
|------|------|---------|------|
| Chemical Science | `sc` | `http://feeds.rsc.org/rss/sc` | ✅ |
| Chemical Society Reviews | `cs` | `http://feeds.rsc.org/rss/cs` | ✅ |
| Chemical Communications | `cc` | `http://feeds.rsc.org/rss/cc` | ✅ |
| Energy & Environmental Science | `ee` | `http://feeds.rsc.org/rss/ee` | ✅ |
| Journal of Materials Chemistry A | `ta` | `http://feeds.rsc.org/rss/ta` | ✅ |
| Journal of Materials Chemistry B | `tb` | `http://feeds.rsc.org/rss/tb` | ✅ |
| Journal of Materials Chemistry C | `tc` | `http://feeds.rsc.org/rss/tc` | ✅ |
| Materials Horizons | `mh` | `http://feeds.rsc.org/rss/mh` | ✅ |
| Nanoscale | `nr` | `http://feeds.rsc.org/rss/nr` | ✅ |
| Nanoscale Horizons | `nh` | `http://feeds.rsc.org/rss/nh` | ✅ |
| Nanoscale Advances | `na` | `http://feeds.rsc.org/rss/na` | ✅ |
| Physical Chemistry Chemical Physics | `cp` | `http://feeds.rsc.org/rss/cp` | ✅ |
| Green Chemistry | `gc` | `http://feeds.rsc.org/rss/gc` | ✅ |
| Polymer Chemistry | `py` | `http://feeds.rsc.org/rss/py` | ✅ |
| Organic Chemistry Frontiers | `qo` | `http://feeds.rsc.org/rss/qo` | ✅ |
| Organic & Biomolecular Chemistry | `ob` | `http://feeds.rsc.org/rss/ob` | ✅ |
| Inorganic Chemistry Frontiers | `qi` | `http://feeds.rsc.org/rss/qi` | ✅ |
| New Journal of Chemistry | `nj` | `http://feeds.rsc.org/rss/nj` | ✅ |
| Natural Product Reports | `np` | `http://feeds.rsc.org/rss/np` | ✅ |
| Analyst | `an` | `http://feeds.rsc.org/rss/an` | ✅ |
| Analytical Methods | `ay` | `http://feeds.rsc.org/rss/ay` | ✅ |
| J. Analytical Atomic Spectrometry | `ja` | `http://feeds.rsc.org/rss/ja` | ✅ |
| Catalysis Science & Technology | `cy` | `http://feeds.rsc.org/rss/cy` | ✅ |
| CrystEngComm | `ce` | `http://feeds.rsc.org/rss/ce` | ✅ |
| Dalton Transactions | `dt` | `http://feeds.rsc.org/rss/dt` | ✅ |
| Faraday Discussions | `fd` | `http://feeds.rsc.org/rss/fd` | ✅ |
| Soft Matter | `sm` | `http://feeds.rsc.org/rss/sm` | ✅ |
| Lab on a Chip | `lc` | `http://feeds.rsc.org/rss/lc` | ✅ |
| Reaction Chemistry & Engineering | `re` | `http://feeds.rsc.org/rss/re` | ✅ |
| Environmental Science: Nano | `en` | `http://feeds.rsc.org/rss/en` | ✅ |
| Environmental Science: Processes & Impacts | `em` | `http://feeds.rsc.org/rss/em` | ✅ |
| Environmental Science: Water Research & Technology | `ew` | `http://feeds.rsc.org/rss/ew` | ✅ |
| Environmental Science: Advances | `va` | `http://feeds.rsc.org/rss/va` | ✅ |
| Environmental Science: Atmospheres | `ea` | `http://feeds.rsc.org/rss/ea` | ✅ |
| Food & Function | `fo` | `http://feeds.rsc.org/rss/fo` | ✅ |
| Materials Chemistry Frontiers | `qm` | `http://feeds.rsc.org/rss/qm` | ✅ |
| Materials Advances | `ma` | `http://feeds.rsc.org/rss/ma` | ✅ |
| Molecular Systems Design & Engineering | `me` | `http://feeds.rsc.org/rss/me` | ✅ |
| RSC Advances | `ra` | `http://feeds.rsc.org/rss/ra` | ✅ |
| RSC Chemical Biology | `cb` | `http://feeds.rsc.org/rss/cb` | ✅ |
| RSC Medicinal Chemistry | `md` | `http://feeds.rsc.org/rss/md` | ✅ |
| RSC Mechanochemistry | `mr` | `http://feeds.rsc.org/rss/mr` | ✅ |
| RSC Pharmaceutics | `pm` | `http://feeds.rsc.org/rss/pm` | ✅ |
| RSC Applied Polymers | `lp` | `http://feeds.rsc.org/rss/lp` | ✅ |
| RSC Applied Interfaces | `lf` | `http://feeds.rsc.org/rss/lf` | ✅ |
| RSC Sustainability | `su` | `http://feeds.rsc.org/rss/su` | ✅ |
| Sustainable Energy & Fuels | `se` | `http://feeds.rsc.org/rss/se` | ✅ |
| Sustainable Food Technology | `fb` | `http://feeds.rsc.org/rss/fb` | ✅ |
| Energy Advances | `ya` | `http://feeds.rsc.org/rss/ya` | ✅ |
| EES Batteries | `eb` | `http://feeds.rsc.org/rss/eb` | ✅ |
| EES Catalysis | `ey` | `http://feeds.rsc.org/rss/ey` | ✅ |
| EES Solar | `el` | `http://feeds.rsc.org/rss/el` | ✅ |
| Sensors & Diagnostics | `sd` | `http://feeds.rsc.org/rss/sd` | ✅ |
| Digital Discovery | `dd` | `http://feeds.rsc.org/rss/dd` | ✅ |
| Industrial Chemistry & Materials | `im` | `http://feeds.rsc.org/rss/im` | ✅ |

> 💡 **RSC 通用规则**：`http://feeds.rsc.org/rss/{CODE}`  
> ⚠️ RSC 的 RSS 链接仅支持 HTTP 协议，使用 HTTPS 无法访问  
> 完整列表：https://pubs.rsc.org/en/ealerts/rssfeed

---

## 五、Wiley 系列

| 期刊 | ISSN | RSS URL | 状态 |
|------|------|---------|------|
| Angewandte Chemie Int. Ed. | 1521-3773 | `https://onlinelibrary.wiley.com/feed/15213773/most-recent` | ✅ |
| Advanced Materials | 1521-4095 | `https://onlinelibrary.wiley.com/feed/15214095/most-recent` | ✅ |
| Advanced Functional Materials | 1616-3028 | `https://onlinelibrary.wiley.com/feed/16163028/most-recent` | ✅ |
| Chemistry - A European Journal | 1521-3765 | `https://onlinelibrary.wiley.com/feed/15213765/most-recent` | ✅ |
| European J. Organic Chemistry | 1099-0690 | `https://onlinelibrary.wiley.com/feed/10990690/most-recent` | ✅ |
| Macromolecular Rapid Communications | 1521-3927 | `https://onlinelibrary.wiley.com/feed/15213927/most-recent` | ✅ |
| Small | 1613-6829 | `https://onlinelibrary.wiley.com/feed/16136829/most-recent` | ✅ |
| Advanced Energy Materials | 1614-6840 | `https://onlinelibrary.wiley.com/feed/16146840/most-recent` | ✅ |
| Advanced Science | 2198-3844 | `https://onlinelibrary.wiley.com/feed/21983844/most-recent` | ✅ |
| ChemSusChem | 1864-564X | `https://onlinelibrary.wiley.com/feed/1864564X/most-recent` | ✅ |
| ChemCatChem | 1867-3899 | `https://onlinelibrary.wiley.com/feed/18673899/most-recent` | ✅ |
| Chemistry - An Asian Journal | 1861-471X | `https://onlinelibrary.wiley.com/feed/1861471X/most-recent` | ✅ |
| InfoMat | 2567-3165 | `https://onlinelibrary.wiley.com/feed/25673165/most-recent` | ✅ |
| Medicinal Research Reviews | 1098-1128 | `https://onlinelibrary.wiley.com/feed/10981128/most-recent` | ✅ |
| Drug Development Research | 1098-2299 | `https://onlinelibrary.wiley.com/feed/10982299/most-recent` | ✅ |
| Archiv der Pharmazie | 1521-4184 | `https://onlinelibrary.wiley.com/feed/15214184/most-recent` | ✅ |
| ChemMedChem | 1860-7179 | `https://chemistry-europe.onlinelibrary.wiley.com/feed/18607187/most-recent` | ✅ |
| Advanced Synthesis & Catalysis | 1615-4169 | `https://advanced.onlinelibrary.wiley.com/feed/16154169/most-recent` | ✅ |
| Asian J. Organic Chemistry | 2193-5815 | `https://aces.onlinelibrary.wiley.com/feed/21935815/most-recent` | ✅ |
| Chinese J. Chemistry | 1614-7065 | `https://onlinelibrary.wiley.com/feed/16147065/most-recent` | ✅ |
| Helvetica Chimica Acta | 1522-2675 | `https://onlinelibrary.wiley.com/feed/15222675/most-recent` | ✅ |
| J. Heterocyclic Chemistry | 1943-5193 | `https://onlinelibrary.wiley.com/feed/19435193/most-recent` | ✅ |
| Clinical Pharmacology & Therapeutics | 1532-6535 | `https://ascpt.onlinelibrary.wiley.com/feed/15326535/most-recent` | ✅ |
| British J. Clinical Pharmacology | 1365-2125 | `https://bpspubs.onlinelibrary.wiley.com/feed/13652125/most-recent` | ✅ |
| Biopharmaceutics & Drug Disposition | 1099-081X | `https://onlinelibrary.wiley.com/feed/1099081X/most-recent` | ✅ |
| Molecular Nutrition & Food Research | 1613-4133 | `https://onlinelibrary.wiley.com/feed/16134133/most-recent` | ✅ |
| J. Food Science | 1750-3841 | `https://onlinelibrary.wiley.com/feed/17503841/most-recent` | ✅ |
| Comprehensive Reviews in Food Science and Food Safety | 1541-4337 | `https://onlinelibrary.wiley.com/feed/15414337/most-recent` | ✅ |
| International J. Food Science & Technology | 1365-2621 | `https://onlinelibrary.wiley.com/feed/13652621/most-recent` | ✅ |
| J. Science of Food and Agriculture | 1097-0010 | `https://onlinelibrary.wiley.com/feed/10970010/most-recent` | ✅ |
| Electroanalysis | 1521-4109 | `https://onlinelibrary.wiley.com/feed/15214109/most-recent` | ✅ |
| Electrophoresis | 1522-2683 | `https://onlinelibrary.wiley.com/feed/15222683/most-recent` | ✅ |
| Mass Spectrometry Reviews | 1098-2787 | `https://onlinelibrary.wiley.com/feed/10982787/most-recent` | ✅ |
| J. Mass Spectrometry | 1096-9888 | `https://onlinelibrary.wiley.com/feed/10969888/most-recent` | ✅ |
| Rapid Comm. Mass Spectrometry | 1097-0231 | `https://onlinelibrary.wiley.com/feed/10970231/most-recent` | ✅ |
| J. Computational Chemistry | 1096-987X | `https://onlinelibrary.wiley.com/feed/1096987X/most-recent` | ✅ |
| Molecular Informatics | 1868-1751 | `https://onlinelibrary.wiley.com/feed/18681751/most-recent` | ✅ |
| Proteomics | 1615-9861 | `https://onlinelibrary.wiley.com/feed/16159861/most-recent` | ✅ |
| Biotechnology and Bioengineering | 1097-0290 | `https://onlinelibrary.wiley.com/feed/10970290/most-recent` | ✅ |

> 💡 **Wiley 通用规则**：`https://onlinelibrary.wiley.com/feed/{ISSN(去连字符)}/most-recent`

---

## 六、Elsevier / ScienceDirect 系列

| 期刊 | ISSN | RSS URL | 状态 |
|------|------|---------|------|
| Tetrahedron | 0040-4020 | `https://rss.sciencedirect.com/publication/science/00404020` | ✅ |
| Tetrahedron Letters | 0040-4039 | `https://rss.sciencedirect.com/publication/science/00404039` | ✅ |
| Carbohydrate Polymers | 0144-8617 | `https://rss.sciencedirect.com/publication/science/01448617` | ✅ |
| Carbohydrate Research | 0008-6215 | `https://rss.sciencedirect.com/publication/science/00086215` | ✅ |
| J. Organometallic Chemistry | 0022-328X | `https://rss.sciencedirect.com/publication/science/0022328X` | ✅ |
| Sensors and Actuators A | 0924-4247 | `https://rss.sciencedirect.com/publication/science/09244247` | ✅ |
| Sensors and Actuators B | 0925-4005 | `https://rss.sciencedirect.com/publication/science/09254005` | ✅ |
| Chemical Engineering Journal | 1385-8947 | `https://rss.sciencedirect.com/publication/science/13858947` | ✅ |
| Journal of Hazardous Materials | 0304-3894 | `https://rss.sciencedirect.com/publication/science/03043894` | ✅ |
| Carbon | 0008-6223 | `https://rss.sciencedirect.com/publication/science/00086223` | ✅ |
| Applied Surface Science | 0169-4332 | `https://rss.sciencedirect.com/publication/science/01694332` | ✅ |
| Coordination Chemistry Reviews | 0010-8545 | `https://rss.sciencedirect.com/publication/science/00108545` | ✅ |
| Progress in Materials Science | 0079-6425 | `https://rss.sciencedirect.com/publication/science/00796425` | ✅ |
| Materials Today | 1369-7021 | `https://rss.sciencedirect.com/publication/science/13697021` | ✅ |
| Biomaterials | 0142-9612 | `https://rss.sciencedirect.com/publication/science/01429612` | ✅ |
| Water Research | 0043-1354 | `https://rss.sciencedirect.com/publication/science/00431354` | ✅ |
| Applied Catalysis B: Environmental | 0926-3373 | `https://rss.sciencedirect.com/publication/science/09263373` | ✅ |
| Energy Storage Materials | 2405-8297 | `https://rss.sciencedirect.com/publication/science/24058297` | ✅ |

### 有机化学 & 天然产物
| 期刊 | ISSN | RSS URL | 状态 |
|------|------|---------|------|
| Bioorganic & Medicinal Chemistry | 0968-0896 | `https://rss.sciencedirect.com/publication/science/09680896` | ✅ |
| Bioorganic & Medicinal Chemistry Letters | 0960-894X | `https://rss.sciencedirect.com/publication/science/0960894X` | ✅ |
| European J. Medicinal Chemistry | 0223-5234 | `https://rss.sciencedirect.com/publication/science/02235234` | ✅ |
| Phytochemistry | 0031-9422 | `https://rss.sciencedirect.com/publication/science/00319422` | ✅ |
| Phytochemistry Letters | 1874-3900 | `https://rss.sciencedirect.com/publication/science/18743900` | ✅ |
| Phytomedicine | 0944-7113 | `https://rss.sciencedirect.com/publication/science/09447113` | ✅ |
| Biochemical Systematics and Ecology | 0305-1978 | `https://rss.sciencedirect.com/publication/science/03051978` | ✅ |
| Current Opinion in Structural Biology | 0959-440X | `https://rss.sciencedirect.com/publication/science/0959440X` | ✅ |

### 药学
| 期刊 | ISSN | RSS URL | 状态 |
|------|------|---------|------|
| Drug Discovery Today | 1359-6446 | `https://rss.sciencedirect.com/publication/science/13596446` | ✅ |
| J. Pharmaceutical Sciences | 0022-3549 | `https://rss.sciencedirect.com/publication/science/00223549` | ✅ |
| European J. Pharmaceutics and Biopharmaceutics | 0939-6411 | `https://rss.sciencedirect.com/publication/science/09396411` | ✅ |
| Int. J. Pharmaceutics | 0378-5173 | `https://rss.sciencedirect.com/publication/science/03785173` | ✅ |
| European J. Pharmaceutical Sciences | 0928-0987 | `https://rss.sciencedirect.com/publication/science/09280987` | ✅ |
| Biochemical Pharmacology | 0006-2952 | `https://rss.sciencedirect.com/publication/science/00062952` | ✅ |
| J. Controlled Release | 0168-3659 | `https://rss.sciencedirect.com/publication/science/01683659` | ✅ |
| Pharmacology & Therapeutics | 0163-7258 | `https://rss.sciencedirect.com/publication/science/01637258` | ✅ |
| Toxicology and Applied Pharmacology | 0041-008X | `https://rss.sciencedirect.com/publication/science/0041008X` | ✅ |
| J. Ethnopharmacology | 0378-8741 | `https://rss.sciencedirect.com/publication/science/03788741` | ✅ |
| Fitoterapia | 0367-326X | `https://rss.sciencedirect.com/publication/science/0367326X` | ✅ |
| Biomedicine & Pharmacotherapy | 0753-3322 | `https://rss.sciencedirect.com/publication/science/07533322` | ✅ |

> 💡 **Elsevier 通用规则**：`https://rss.sciencedirect.com/publication/science/{ISSN(去连字符)}`   
> 进入期刊主页 → Articles & Issues → 获取 RSS 链接

### 食品科学
| 期刊 | ISSN | RSS URL | 状态 |
|------|------|---------|------|
| Food Chemistry | 0308-8146 | `https://rss.sciencedirect.com/publication/science/03088146` | ✅ |
| Food Research International | 0963-9969 | `https://rss.sciencedirect.com/publication/science/09639969` | ✅ |
| Food Hydrocolloids | 0268-005X | `https://rss.sciencedirect.com/publication/science/0268005X` | ✅ |
| Food Control | 0956-7135 | `https://rss.sciencedirect.com/publication/science/09567135` | ✅ |
| Food and Chemical Toxicology | 0278-6915 | `https://rss.sciencedirect.com/publication/science/02786915` | ✅ |
| LWT - Food Science and Technology | 0023-6438 | `https://rss.sciencedirect.com/publication/science/00236438` | ✅ |
| J. Food Composition and Analysis | 0889-1575 | `https://rss.sciencedirect.com/publication/science/08891575` | ✅ |
| Food Bioscience | 2212-4292 | `https://rss.sciencedirect.com/publication/science/22124292` | ✅ |

### 分析化学
| 期刊 | ISSN | RSS URL | 状态 |
|------|------|---------|------|
| Analytica Chimica Acta | 0003-2670 | `https://rss.sciencedirect.com/publication/science/00032670` | ✅ |
| Talanta | 0039-9140 | `https://rss.sciencedirect.com/publication/science/00399140` | ✅ |
| J. Chromatography A | 0021-9673 | `https://rss.sciencedirect.com/publication/science/00219673` | ✅ |
| J. Chromatography B | 1570-0232 | `https://rss.sciencedirect.com/publication/science/15700232` | ✅ |
| TrAC - Trends in Analytical Chemistry | 0165-9936 | `https://rss.sciencedirect.com/publication/science/01659936` | ✅ |
| Microchemical J. | 0026-265X | `https://rss.sciencedirect.com/publication/science/0026265X` | ✅ |
| Biosensors and Bioelectronics | 0956-5663 | `https://rss.sciencedirect.com/publication/science/09565663` | ✅ |
| J. Electroanalytical Chemistry | 1572-6657 | `https://rss.sciencedirect.com/publication/science/15726657` | ✅ |
| Spectrochimica Acta A | 1386-1425 | `https://rss.sciencedirect.com/publication/science/13861425` | ✅ |
| Spectrochimica Acta B | 0584-8547 | `https://rss.sciencedirect.com/publication/science/05848547` | ✅ |
| J. Pharmaceutical and Biomedical Analysis | 0731-7085 | `https://rss.sciencedirect.com/publication/science/07317085` | ✅ |

### 计算化学 & 生物信息学
| 期刊 | ISSN | RSS URL | 状态 |
|------|------|---------|------|
| Artificial Intelligence in Medicine | 0933-3657 | `https://rss.sciencedirect.com/publication/science/09333657` | ✅ |
| Computers in Biology and Medicine | 0010-4825 | `https://rss.sciencedirect.com/publication/science/00104825` | ✅ |
| J. Biomedical Informatics | 1532-0464 | `https://rss.sciencedirect.com/publication/science/15320464` | ✅ |
| Chemometrics and Intelligent Laboratory Systems | 0169-7439 | `https://rss.sciencedirect.com/publication/science/01697439` | ✅ |
| Computational Biology and Chemistry | 1476-9271 | `https://rss.sciencedirect.com/publication/science/14769271` | ✅ |

---

## 七、APS (American Physical Society)

| 期刊 | Code | RSS URL | 状态 |
|------|------|---------|------|
| Physical Review Letters | `prl` | `https://feeds.aps.org/rss/recent/prl.xml` | ✅ |
| Physical Review X | `prx` | `https://feeds.aps.org/rss/recent/prx.xml` | ✅ |
| Physical Review A | `pra` | `https://feeds.aps.org/rss/recent/pra.xml` | ✅ |
| Physical Review B | `prb` | `https://feeds.aps.org/rss/recent/prb.xml` | ✅ |
| Physical Review C | `prc` | `https://feeds.aps.org/rss/recent/prc.xml` | ✅ |
| Physical Review D | `prd` | `https://feeds.aps.org/rss/recent/prd.xml` | ✅ |
| Physical Review E | `pre` | `https://feeds.aps.org/rss/recent/pre.xml` | ✅ |
| Physical Review Applied | `prapplied` | `https://feeds.aps.org/rss/recent/prapplied.xml` | ✅ |
| Physical Review Materials | `prmaterials` | `https://feeds.aps.org/rss/recent/prmaterials.xml` | ✅ |
| Physical Review Fluids | `prfluids` | `https://feeds.aps.org/rss/recent/prfluids.xml` | ✅ |
| Physical Review Research | `prresearch` | `https://feeds.aps.org/rss/recent/prresearch.xml` | ✅ |
| Physical Review Accelerators and Beams | `prstab` | `https://feeds.aps.org/rss/recent/prstab.xml` | ✅ |
| Physical Review Physics Education Research | `prstper` | `https://feeds.aps.org/rss/recent/prstper.xml` | ✅ |
| PRX Energy | `prxenergy` | `https://feeds.aps.org/rss/recent/prxenergy.xml` | ✅ |
| PRX Life | `prxlife` | `https://feeds.aps.org/rss/recent/prxlife.xml` | ✅ |
| PRX Quantum | `prxquantum` | `https://feeds.aps.org/rss/recent/prxquantum.xml` | ✅ |
| Reviews of Modern Physics | `rmp` | `https://feeds.aps.org/rss/recent/rmp.xml` | ✅ |
| Physics Magazine | `physics` | `https://feeds.aps.org/rss/recent/physics.xml` | ✅ |

> 📎 **专题分类**：APS还提供子领域RSS，如PRL凝聚态 `tocsec/PRL-CondensedMatterStructureetc.xml`，详见 https://journals.aps.org/feeds

---

## 八、Cell Press & 其他顶刊

| 期刊 | RSS URL | 状态 |
|------|---------|------|
| Cell | `https://www.cell.com/cell/current.rss` | ✅ |
| Chem | `https://www.cell.com/chem/current.rss` | ✅ |
| Joule | `https://www.cell.com/joule/current.rss` | ✅ |
| Matter | `https://www.cell.com/matter/current.rss` | ✅ |
| Cell Reports | `https://www.cell.com/cell-reports/current.rss` | ✅ |
| Cell Reports Physical Science | `https://www.cell.com/cell-reports-physical-science/current.rss` | ✅ |
| Cell Reports Medicine | `https://www.cell.com/cell-reports-medicine/current.rss` | ✅ |
| Patterns | `https://www.cell.com/patterns/current.rss` | ✅ |
| iScience | `https://www.cell.com/iscience/current.rss` | ✅ |
| Molecular Cell | `https://www.cell.com/molecular-cell/current.rss` | ✅ |
| Cancer Cell | `https://www.cell.com/cancer-cell/current.rss` | ✅ |
| Neuron | `https://www.cell.com/neuron/current.rss` | ✅ |
| Immunity | `https://www.cell.com/immunity/current.rss` | ✅ |
| Cell Genomics | `https://www.cell.com/cell-genomics/current.rss` | ✅ |
| PNAS | `https://www.pnas.org/action/showFeed?type=etoc&feed=rss` | ✅ |
| Current Biology | `https://www.cell.com/current-biology/current.rss` | ✅ |
| Cell Chemical Biology | `https://www.cell.com/cell-chemical-biology/current.rss` | ✅ |
| Cell Host & Microbe | `https://www.cell.com/cell-host-microbe/current.rss` | ✅ |
| Cell Systems | `https://www.cell.com/cell-systems/current.rss` | ✅ |
| Stem Cell Reports | `https://www.cell.com/stem-cell-reports/current.rss` | ✅ |
| Biophysical Journal | `https://www.cell.com/biophysj/current.rss` | ✅ |
| Molecular Plant | `https://www.cell.com/molecular-plant/current.rss` | ✅ |
| Structure | `http://rss.sciencedirect.com/publication/science/09692126` | ✅ |

> 💡 **Cell Press 通用规则**：`https://www.cell.com/{期刊名}/current.rss`  
> 期刊名从URL复制（如 `chem`、`joule`、`matter`）

---

## 九、Thieme 化学期刊

| 期刊 | RSS URL | 状态 |
|------|---------|------|
| Synlett | `https://www.thieme-connect.de/rss/thieme/en/10.1055-s-00000083.xml` | ✅ |
| Synthesis | `https://www.thieme-connect.de/rss/thieme/en/10.1055-s-00000084.xml` | ✅ |
| Synfacts | `https://www.thieme-connect.de/rss/thieme/en/10.1055-s-00000085.xml` | ✅ |
| Organic Materials | `https://www.thieme-connect.de/rss/thieme/en/10.1055-s-00000146.xml` | ✅ |
| Planta Medica | `https://www.thieme-connect.de/rss/thieme/en/10.1055-s-00000056.xml` | ✅ |

> 💡 **Thieme 通用规则**：`https://www.thieme-connect.de/rss/thieme/en/{期刊ID}.xml`
> 各期刊ID：Synlett=`s-00000083`, Synthesis=`s-00000084`, Synfacts=`s-00000085`, Organic Materials=`s-00000146`, Planta Medica=`s-00000056`

---

## 十、生命科学综合

### eLife
| 期刊 | RSS URL | 状态 |
|------|---------|------|
| eLife | `https://elifesciences.org/rss/ahead.xml` | ✅ |

### PLOS (Public Library of Science)
| 期刊 | RSS URL | 状态 |
|------|---------|------|
| PLOS Biology | `https://journals.plos.org/plosbiology/feed/atom` | ✅ |
| PLOS ONE | `https://journals.plos.org/plosone/feed/atom` | ✅ |
| PLOS Genetics | `https://journals.plos.org/plosgenetics/feed/atom` | ✅ |
| PLOS Pathogens | `https://journals.plos.org/plospathogens/feed/atom` | ✅ |
| PLOS Computational Biology | `https://journals.plos.org/ploscompbiol/feed/atom` | ✅ |

### Springer 药学
| 期刊 | RSS URL | 状态 |
|------|---------|------|
| Pharmaceutical Research | `https://link.springer.com/search.rss?search-within=Journal&facet-journal-id=11095` | ✅ |
| J. Computer-Aided Molecular Design | `https://link.springer.com/search.rss?search-within=Journal&facet-journal-id=10822` | ✅ |
| J. Pharmaceutical & Biomedical Analysis | `https://link.springer.com/search.rss?search-within=Journal&facet-journal-id=12365` | ✅ |
| AAPS PharmSciTech | `https://link.springer.com/search.rss?search-within=Journal&facet-journal-id=12249` | ✅ |
| Clinical Pharmacokinetics | `https://link.springer.com/search.rss?search-within=Journal&facet-journal-id=40262` | ✅ |
| J. Natural Medicines | `https://link.springer.com/search.rss?search-within=Journal&facet-journal-id=11418` | ✅ |
| European Food Research and Technology | `https://link.springer.com/search.rss?search-within=Journal&facet-journal-id=217` | ✅ |
| Phytochemistry Reviews | `https://link.springer.com/search.rss?search-within=Journal&facet-journal-id=11101` | ✅ |
| Natural Products and Bioprospecting | `https://link.springer.com/search.rss?search-within=Journal&facet-journal-id=13659` | ✅ |
| Analytical and Bioanalytical Chemistry | `https://link.springer.com/search.rss?search-within=Journal&facet-journal-id=216` | ✅ |
| Analytical Sciences | `https://link.springer.com/search.rss?search-within=Journal&facet-journal-id=44211` | ✅ |
| Chromatographia | `https://link.springer.com/search.rss?search-within=Journal&facet-journal-id=373` | ✅ |

### 计算 & 生物信息
| 期刊 | RSS URL | 状态 |
|------|---------|------|
| J. Cheminformatics | `https://link.springer.com/search.rss?search-within=Journal&facet-journal-id=13321` | ✅ |
| BMC Bioinformatics | `https://link.springer.com/search.rss?search-within=Journal&facet-journal-id=12859` | ✅ |
| BMC Medical Informatics and Decision Making | `https://link.springer.com/search.rss?search-within=Journal&facet-journal-id=12911` | ✅ |

---

## 十一、Oxford Academic (OUP)

| 期刊 | RSS URL | 状态 |
|------|---------|------|
| Bioinformatics | `https://academic.oup.com/rss/site_5139/3001.xml` | ✅ |
| Briefings in Bioinformatics | `https://academic.oup.com/rss/site_5143/3005.xml` | ✅ |

> 🔑 OUP RSS 格式：`https://academic.oup.com/rss/site_{SITE_ID}/{FEED_ID}.xml`   
> 已知示例：Bioinformatics 为 `site_5139/3001.xml`，Nucleic Acids Research 为 `site_5127/3091.xml`，JAMIA 为 `site_5396/3257.xml`

---

## 十二、MDPI (Multidisciplinary Digital Publishing Institute)

| 期刊 | RSS URL | 状态 |
|------|---------|------|
| AI | `https://www.mdpi.com/ai/rss` | ✅ |
| AI Chemistry | `https://www.mdpi.com/aichem/rss` | ✅ |

> 💡 **MDPI 通用规则**：`https://www.mdpi.com/{期刊简写}/rss`

---

## 十三、Taylor & Francis 药学

| 期刊 | RSS URL | 状态 |
|------|---------|------|
| Expert Opinion on Drug Delivery | `https://www.tandfonline.com/feed/rss/iedd20` | ✅ |
| Drug Metabolism Reviews | `https://www.tandfonline.com/feed/rss/idmr20` | ✅ |
| J. Asian Natural Products Research | `https://www.tandfonline.com/feed/rss/ganp20` | ✅ |
| Critical Reviews in Food Science and Nutrition | `https://www.tandfonline.com/feed/rss/bfsn20` | ✅ |
| Analytical Letters | `https://www.tandfonline.com/feed/rss/lanl20` | ✅ |
| Critical Reviews in Analytical Chemistry | `https://www.tandfonline.com/feed/rss/batc20` | ✅ |

---

## 十四、ASPET (American Society for Pharmacology and Experimental Therapeutics)

| 期刊 | RSS URL | 状态 |
|------|---------|------|
| Drug Metabolism & Disposition | `https://dmd.aspetjournals.org/action/showFeed?type=etoc&feed=rss&jc=dmd` | ✅ |
| J. Pharmacology & Experimental Therapeutics | `https://jpet.aspetjournals.org/action/showFeed?type=etoc&feed=rss&jc=jpet` | ✅ |

---

## 十五、预印本

### arXiv
| 分类 | RSS URL | 状态 |
|------|---------|------|
| cs.AI | `https://rss.arxiv.org/rss/cs.AI` | ✅ |
| cs.LG | `https://rss.arxiv.org/rss/cs.LG` | ✅ |
| cs.CV | `https://rss.arxiv.org/rss/cs.CV` | ✅ |
| cs.CL | `https://rss.arxiv.org/rss/cs.CL` | ✅ |
| cs.NE | `https://rss.arxiv.org/rss/cs.NE` | ✅ |
| cs.RO | `https://rss.arxiv.org/rss/cs.RO` | ✅ |
| stat.ML | `https://rss.arxiv.org/rss/stat.ML` | ✅ |
| physics.chem-ph | `https://rss.arxiv.org/rss/physics.chem-ph` | ✅ |
| physics.comp-ph | `https://rss.arxiv.org/rss/physics.comp-ph` | ✅ |
| physics.app-ph | `https://rss.arxiv.org/rss/physics.app-ph` | ✅ |
| cond-mat.mtrl-sci | `https://rss.arxiv.org/rss/cond-mat.mtrl-sci` | ✅ |
| cond-mat.soft | `https://rss.arxiv.org/rss/cond-mat.soft` | ✅ |
| q-bio.QM | `https://rss.arxiv.org/rss/q-bio.QM` | ✅ |
| q-bio.BM | `https://rss.arxiv.org/rss/q-bio.BM` | ✅ |
| eess.IV | `https://rss.arxiv.org/rss/eess.IV` | ✅ |

> 💡 **arXiv 通用规则**：`https://rss.arxiv.org/rss/{分类名}`  
> Atom格式：`https://rss.arxiv.org/atom/{分类名}`  
> 所有分类列表：https://arxiv.org/category_taxonomy  
> 新版API feed：`https://export.arxiv.org/rss/{分类名}`

### bioRxiv
| 学科 | RSS URL | 状态 |
|------|---------|------|
| All | `https://connect.biorxiv.org/biorxiv_xml.php?subject=` | ✅ |
| Biochemistry | `https://connect.biorxiv.org/biorxiv_xml.php?subject=biochemistry` | ✅ |
| Bioinformatics | `https://connect.biorxiv.org/biorxiv_xml.php?subject=bioinformatics` | ✅ |
| Biophysics | `https://connect.biorxiv.org/biorxiv_xml.php?subject=biophysics` | ✅ |
| Cell Biology | `https://connect.biorxiv.org/biorxiv_xml.php?subject=cell_biology` | ✅ |
| Genomics | `https://connect.biorxiv.org/biorxiv_xml.php?subject=genomics` | ✅ |
| Synthetic Biology | `https://connect.biorxiv.org/biorxiv_xml.php?subject=synthetic_biology` | ✅ |
| Systems Biology | `https://connect.biorxiv.org/biorxiv_xml.php?subject=systems_biology` | ✅ |
| Neuroscience | `https://connect.biorxiv.org/biorxiv_xml.php?subject=neuroscience` | ✅ |
| Immunology | `https://connect.biorxiv.org/biorxiv_xml.php?subject=immunology` | ✅ |
| Molecular Biology | `https://connect.biorxiv.org/biorxiv_xml.php?subject=molecular_biology` | ✅ |
| Pharmacology and Toxicology | `https://connect.biorxiv.org/biorxiv_xml.php?subject=pharmacology_and_toxicology` | ✅ |
| Plant Biology | `https://connect.biorxiv.org/biorxiv_xml.php?subject=plant_biology` | ✅ |
| Genetics | `https://connect.biorxiv.org/biorxiv_xml.php?subject=genetics` | ✅ |
| 组合示例(Genomics+Bioinformatics) | `https://connect.biorxiv.org/biorxiv_xml.php?subject=genomics+bioinformatics` | ✅ |

> 💡 **bioRxiv 通用规则**：`https://connect.biorxiv.org/biorxiv_xml.php?subject={学科}`  
> 多词学科用下划线：`cell_biology`  
> 组合多个学科用`+`号

### medRxiv
| 学科 | RSS URL | 状态 |
|------|---------|------|
| All | `https://connect.medrxiv.org/medrxiv_xml.php?subject=` | ✅ |
| Epidemiology | `https://connect.medrxiv.org/medrxiv_xml.php?subject=epidemiology` | ✅ |
| Infectious Diseases | `https://connect.medrxiv.org/medrxiv_xml.php?subject=infectious_diseases` | ✅ |
| Oncology | `https://connect.medrxiv.org/medrxiv_xml.php?subject=oncology` | ✅ |
| Public and Global Health | `https://connect.medrxiv.org/medrxiv_xml.php?subject=public_and_global_health` | ✅ |
| Health Informatics | `https://connect.medrxiv.org/medrxiv_xml.php?subject=health_informatics` | ✅ |
| Cardiovascular Medicine | `https://connect.medrxiv.org/medrxiv_xml.php?subject=cardiovascular_medicine` | ✅ |
| Neurology | `https://connect.medrxiv.org/medrxiv_xml.php?subject=neurology` | ✅ |
| Psychiatry and Clinical Psychology | `https://connect.medrxiv.org/medrxiv_xml.php?subject=psychiatry_and_clinical_psychology` | ✅ |
| Radiology and Imaging | `https://connect.medrxiv.org/medrxiv_xml.php?subject=radiology_and_imaging` | ✅ |

> 💡 **medRxiv 通用规则**：`https://connect.medrxiv.org/medrxiv_xml.php?subject={学科}`

### chemRxiv
| 类型 | RSS URL | 状态 |
|------|---------|------|
| Latest | `https://chemrxiv.org/action/showFeed?type=latest&format=rss` | ✅ |

---

## 十六、其他出版商

### Springer
> 格式：`https://link.springer.com/search.rss?search-within=Journal&facet-journal-id={ID}`
> 进入期刊主页 → 获得 `facet-journal-id` 参数 → 构造RSS链接

### IEEE
> 格式：`https://ieeexplore.ieee.org/rss/TOC{JOURNAL_NUMBER}.XML`
> 浏览：https://ieeexplore.ieee.org/browse/periodicals/title → 选择期刊获取

### IOP (Institute of Physics)
> 浏览：https://iopscience.iop.org/journalList → 选择期刊获取RSS

### MDPI
> 每个期刊主页直接有RSS图标，格式不统一，从 https://www.mdpi.com/about/journals 浏览获取

### ACM
> 浏览：https://dl.acm.org/journals → 选择期刊获取

---

## 十七、中文期刊（知网）

| 来源 | RSS URL 模式 |
|------|-------------|
| 知网期刊 | 访问 https://navi.cnki.net/knavi/journals/index → 选择期刊 → 点击 RSS 订阅 |

---

## 📊 统计数据

| 出版商 | 收录条数 |
|--------|---------|
| Nature 系列 | 34 |
| Science 系列 | 6 |
| ACS | 88 |
| RSC | 54 |
| Wiley | 39 |
| Elsevier / ScienceDirect | 62 |
| APS | 18 |
| Cell Press | 23 |
| Thieme | 5 |
| 生命科学综合 (eLife/PLOS/Springer) | 21 |
| 预印本 (arXiv/bioRxiv/medRxiv/chemRxiv) | 40+ |
| 学术会议 (WikiCFP) | 10+ 分类 |
| Taylor & Francis (药学) | 6 |
| ASPET (药理与实验治疗) | 2 |
| Oxford Academic (OUP) | 2 |
| MDPI | 2 |
| **总计** | **422+** |
