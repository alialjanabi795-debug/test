# تقرير المرحلتين A وB — ربط أداة الأدلة بـ CodeRAG-Bench

**الحالة:**
- Phase A مكتملة.
- Phase B نُفّذت بعد موافقة المستخدم على البنود 1–6 في القسم 9.
- النتيجة: **615 عينة مقيَّمة بالتنفيذ الحقيقي، نجح منها 0** (Qwen2.5-Coder-0.5B على 8 مهام ODEX-en). التفاصيل في القسم 12.
- الأقسام 1–8 تصف حالة Phase A كما كانت قبل التنزيلات.

تاريخ الفحص: 2026-10-21. الفرع: `claude/coderag-bench-pilot-7ws2nh`.

---

## 1) العتاد

| البند | القيمة المقاسة |
|---|---|
| CPU | 4 vCPU، Intel Xeon @ 2.80GHz (KVM)، يدعم AVX2/AVX-512 |
| RAM | 15 GiB، بلا Swap |
| GPU | لا يوجد (لا `nvidia-smi` ولا `/dev/nvidia*`) |
| القرص | 29 GiB متاحة (بعد الاستنساخ) |
| OS | Ubuntu 24.04.5 LTS، Linux 6.18.44 |

## 2) البيئة

- Python النظام: 3.13.16 (ويوجد `/usr/bin/python3.11`). المستودع الرسمي يطلب Python 3.10.
- الحزم المثبتة: numpy 2.5.3 وpandas 3.0.5 وغيرها. **لا يوجد** torch أو transformers أو datasets أو rank_bm25 أو vllm أو accelerate.
- `uv` 0.11.32 متاح، ويمكنه تنزيل CPython 3.10.20.
- git 2.43.0.
- Docker client 29.9.1 مثبت، لكن الـdaemon لا يعمل. لم أشغّله، ولا حاجة إليه.
- أدوات util-linux متاحة (`unshare` و`setpriv` و`prlimit`)، والجلسة تعمل بصلاحية root مع جميع الـcapabilities.
- **لا يوجد LLM محلي** ولا أي ملفات أوزان (`*.safetensors` أو `*.gguf` أو `*.bin`)، ولا ذاكرة HF cache.
- الشبكة عبر proxy: huggingface.co وgithub.com وdownload.pytorch.org وpypi قابلة للوصول.

## 3) CodeRAG-Bench الرسمي

- لم يكن موجوداً محلياً. استنسخته **للقراءة فقط** في مجلد scratch:
  `https://github.com/code-rag-bench/code-rag-bench` @ **`f9e100ca9ed94b8f1983b356ae81966e30210cf4`** (2024-11-15، "Merge pull request #4").
- **ملاحظة شفافية:** الاستنساخ أخذ 1.2 GB على القرص (منها `.git` بحجم 326 MB وملفات devdocs خام)، أي أكثر مما توقعت لاستنساخ "كود فقط". لم أنفّذ منه أي سكربت تنزيل.
- **المستودع الرسمي لم يُعدَّل.** `run_manifest.py` يرفض التشغيل إذا كان الـSHA مختلفاً أو كانت النسخة dirty.
- لا توجد أي مجموعات بيانات benchmark محلياً، باستثناء الملفات المرفقة داخل المستودع:
  `retrieval/datasets/canonical/odex_docs.json` (439 سجلاً) و`ds1000_docs.json` (1000 سجل)، وفيها وثائق Gold.

## 4) ما وجدته في الكود الرسمي (الـschema والـadapter)

**صيغة نتائج الاسترجاع (التي يقرأها `generation/main.py`):**
- الملف هو نفس سجلات المهمة الأصلية (مثل `neulab/odex`) مع عمود إضافي `docs`.
- `docs` قائمة مرتبة حسب الـrank، وكل عنصر هو نص الـcorpus كاملاً `{"title", "text"}`.
- **الملف لا يحتفظ بالـscore ولا بالـcorpus id** (`get_top_docs` في `eval_beir_*.py`). لذلك يحتفظ الـadapter بهما بنفسه.
- طريقة الاستدعاء: `main.py --dataset_path json --data_files_test <file> --topk_docs K`.

**توليد الـprompt (`eval/tasks/odex.py`):**
- `context = "Please refer to the following documentation to generate the code:\n" + "\n".join(ctx["text"] for ctx in docs[:topk])`.
- `prompt = context + "\n" + function_head+docstring`.
- في حالة No-Retrieval تكون `docs=[]`، فيصبح `context=""`.

**التقييم الرسمي لـODEX:**
- `custom_metrics/code_eval.compute_code_eval`، وفيه `exec` داخل `multiprocessing` مع `reliability_guard` ومهلة 3.0 ثوانٍ.
- المستودع نفسه يصرّح بأن هذا **ليس sandbox أمنياً**.

**مشكلات توافق موثّقة:**
1. `eval/tasks/__init__.py` يستورد كل المهام مرة واحدة، ومنها SWE-bench التي تحتاج GitPython. الحل: `crag_upstream.py` يسجّل package shells ليحمّل ملفات المستودع الأصلية نفسها دون تنفيذ `__init__`، **بلا نسخ وبلا patch**.
2. `eval/generation.py` ينشئ `OpenAI()` عند الاستيراد، فيفشل بلا مفتاح API. لذلك أعدت كتابة `EndOfFunctionCriteria` في `run_manifest.py` بنفس المنطق حرفياً (10 أسطر).
3. `TokenizedDataset` في المستودع يقتطع الـprompt **بصمت** (`truncation=True` و`max_length_input` بقيمة افتراضية 512، والاقتطاع من اليسار). الـadapter **لا يقتطع أبداً**: يقيس الطول الفعلي، وإن تجاوز الحد يسجّل الحالة في `skipped.jsonl` مع السبب.
4. الـ`task_id` في ODEX ليس فريداً: 333 قيمة مميزة من 439 سجلاً، و66 منها مكررة. استخدمت المعرّف `"{index}_{task_id}"` كما يفعل `retrieval/create/odex.py`.
5. **ODEX وDS-1000 فيهما split اختبار فقط، ولا يوجد dev split رسمي.** "مهام التطوير" في هذا الـpilot شريحة ثابتة من test تُختار بقاعدة مكتوبة مسبقاً (القسم 7). لا يوجد تدريب ولا ضبط hyperparameters. ويجب استبعاد هذه الشريحة من أي تقييم نهائي لاحق.
6. **DS-1000 مؤجل:**
   - `eval/tasks/ds1000.py` ينزّل وقت التشغيل الـharness القديم والبيانات من `HKUNLP/DS-1000@49c1c543`.
   - هذا الـharness يتطلب إصدارات قديمة مثبتة من المكتبات (حقبة Python 3.7، ومعها TensorFlow وPyTorch قديمة)، أي تثبيتاً ثقيلاً.
   - ملف `ds1000_docs.json` المرفق في المستودع بصيغة أحدث (`metadata` و`code_context`). **لم أتحقق** من محاذاته مع ترتيب الـharness القديم.
   - التوصية: الـsmoke test على ODEX-en فقط.

## 5) الـSandbox (البند 4 في المهمة)

بُني `sandbox.py` من أدوات موجودة مسبقاً فقط، دون تنزيل أي شيء. الكود المنفَّذ يعمل بهذه القيود:
- namespaces جديدة: net وmount وpid وipc وuts.
- المستخدم `nobody`، و`CapEff=0`، و`no_new_privs`، وبيئة متغيرات فارغة.
- `/` و`/usr` و`/dev` للقراءة فقط.
- `/root` و`/home` و`/run` مخفية خلف tmpfs فارغ، فلا وصول إلى بيانات الاعتماد ولا إلى git checkout.
- `/tmp` و`/dev/shm` من نوع tmpfs جديد.
- المجلد الوحيد القابل للكتابة هو مجلد الـjob.
- حدود الموارد: ذاكرة 4 GiB، وCPU 300 ثانية، و256 عملية، وحجم ملف 64 MiB، و512 ملفاً مفتوحاً، مع مهلة wall-clock.

**الاختبار الذاتي** (`python3 sandbox.py` → `SANDBOX_SELF_TEST PASS`):
- كل محاولات الشبكة فشلت: proxy على loopback، وIP عام، وDNS.
- كل محاولات الكتابة على المستودع و`/` و`/usr` والـbind للقراءة فقط فشلت.
- قراءة `/root/.claude.json` و`.gitconfig` فشلت.
- تخصيص 6 GiB فشل.
- PID واحد مرئي فقط.

**تشغيل المقيِّم الرسمي داخل الـSandbox** (حلول مرجعية من benchmark، وليس كوداً مولَّداً):
- 8 مهام ODEX: كل الحلول المرجعية **passed**، وكل الحلول الخاطئة عمداً **failed**.
- كود يحاول الاتصال بالشبكة: `failed: [Errno 101] Network is unreachable`.
- حلقة لا نهائية: `timed out`.

**حدود يجب ذكرها:**
- هذه عزلة على مستوى العمليات، وليست VM.
- الكود المرشح يعمل كعملية ابن داخل عملية المقيِّم، وهذا تصميم المستودع الرسمي. لذلك يمكن نظرياً أن يكتب فوق ملف النتائج. فحص مفاتيح النتائج يكشف العبث الفادح فقط، ولا يكشف تزويراً متعمداً.
- النتيجة: **الـSandbox موثوق بما يكفي لنموذج صغير في smoke test**. لكنه ليس ضماناً ضد كود عدائي مصمم خصيصاً.

## 6) الكود المضاف (ملفات المستودع الحالي)

| الملف | الدور |
|---|---|
| `sandbox.py` | عزل namespaces + `self_test()` |
| `sandbox_eval.py`, `sandbox_eval_runner.py` | تشغيل `compute_code_eval` الرسمي داخل الـSandbox، مع نتيجة لكل عينة على حدة |
| `crag_upstream.py` | استيراد وحدات المستودع الرسمي دون تعديله، مع تثبيت الـSHA |
| `odex_adapter.py` | معرّفات المهام، وقاعدة الاختيار، وإنشاء `GeneralODEX` الرسمي عبر `dataset_path=json` |
| `select_tasks.py` | اختيار الشريحة بقاعدة ثابتة، مع خيار التحقق من الحلول المرجعية في الـSandbox |
| `retrieve_bm25.py` | BM25Okapi مطابق لـ`eval_beir_okapibm25.py`، مع حفظ id وscore وrank ونص الوثيقة وبصمة الفهرس |
| `normalize_candidates.py` | تحويل ناتج الاسترجاع إلى `candidates.jsonl` بصيغة README، مع عدّ التوكنات بـtokenizer المولّد |
| `run_manifest.py` | التوليد والتقييم لكل صف في الـmanifest ولكل عينة، وكتابة `results.jsonl` و`skipped.jsonl` و`raw/`، مع إمكانية الاستئناف |
| `positive_control.py` | ضابط إيجابي: الحل المرجعي عبر نفس مسار المعالجة والتقييم |
| `test_adapters.py` | 12 اختباراً offline (2 منها تتخطى الآن لغياب torch/datasets) |

الملفات الأصلية للـpilot (`prepare_manifest.py` و`analyze_pilot.py` و`test_pilot.py`) **لم تُعدَّل**.

## 7) خطة Phase B (نُفّذت كما هي؛ النتائج في القسم 12)

1. **قاعدة اختيار المهام (مكتوبة قبل أي توليد):**
   - مهام ODEX-en بترتيب الملف.
   - مكتباتها كلها من stdlib، دون مكتبات ذات أثر جانبي (os وsubprocess وsocket وurllib وsys وtime...).
   - لكل مهمة وثيقة canonical واحدة على الأقل.
   - الحل المرجعي ينجح في الـSandbox.
   - نأخذ أول 8 مهام تحقق ذلك. **انحياز اختيار معروف:** مهام stdlib فقط.
2. **الاسترجاع:** BM25Okapi (`rank_bm25`) على corpus `docprompting-conala` كاملاً، والـquery هي `intent`، ونأخذ top-5. الفهرس مجمّد وبصمته محفوظة.
3. **الـmanifest:** `prepare_manifest.py --topn 5 --max-docs 2 --budget 4096`، أي حتى 16 حالة لكل مهمة.
4. **التشغيل:** فحص No-Retrieval أولاً لمهمة واحدة (`--only-subsets none --limit-tasks 1`)، ثم الكل.
   - إعدادات المستودع الافتراضية: `do_sample=True` و`T=0.2` و`top_p=0.95` و`top_k=0`.
   - `max_new_tokens=256` (انحراف موثّق: المستودع يستخدم `max_length` شاملاً للـprompt، وهذا يجعل ميزانية التوليد غير متساوية بين الحالات).
   - 5 عينات، و`sample_id` من 0 إلى 4، و`seed=sample_id`.
   - **تطابق الـseed لا يعني تطابق مسارات العينات عبر prompts مختلفة.**
5. **الحجم:** حتى 8 × 16 × 5 = 640 عملية توليد. لم أقِس سرعة النموذج بعد، وسأقيسها من فحص No-Retrieval قبل الالتزام بالتشغيل الكامل.

## 8) الأوامر المنفذة فعلاً (Phase A)

```bash
uname -a; lscpu; free -h; df -h; nvidia-smi; python3 --version; pip list; docker info; uv python list
git clone https://github.com/code-rag-bench/code-rag-bench.git   # scratch, قراءة فقط
curl https://huggingface.co/api/{datasets,models}/...            # metadata فقط (أحجام وSHA)
curl .../neulab/odex/resolve/c3741a6.../odex.py ; .../docprompting-conala/resolve/48df7ab.../docprompting-conala.py  # سكربتات تحميل (بضعة KB) للقراءة
python3 sandbox.py                                                # SANDBOX_SELF_TEST PASS
python3 <scratch>/ref_check.py                                    # المقيِّم الرسمي داخل الـSandbox على حلول مرجعية
python3 test_pilot.py ; CRAG_UPSTREAM=<checkout> python3 test_adapters.py   # OK
```

## 9) الموافقات المطلوبة — **وافق عليها المستخدم جميعاً** ("Approve all"، `Qwen2.5-Coder-0.5B`، "Allow in sandbox")

| # | الطلب | الحجم التقريبي | المبرر |
|---|---|---|---|
| 1 | CPython 3.10.20 عبر `uv`، مثبت تحت `/srv/crag/python` | نحو 30 MB | المستودع الرسمي مبني لـ3.10، والـSandbox يخفي `/root` |
| 2 | venv في `/srv/crag/venv`: `torch==2.3.1+cpu` (من فهرس PyTorch CPU) و`transformers==4.40.0` (تثبيت المستودع) و`datasets==2.19.2` و`numpy==1.26.4` و`rank_bm25==0.2.2` و`tqdm` و`accelerate` | تنزيل نحو 350 MB، ونحو 1.2 GB بعد التثبيت | التوليد على CPU، وتحميل `GeneralODEX` الرسمي، وBM25 الرسمي |
| 3 | بيانات `neulab/odex` (`en_test.jsonl`) @ `c3741a66c486b1a23beefdf6c75b06dba288d4f9` | أقل من 1 MB | سجلات المهام والاختبارات الرسمية |
| 4 | corpus `neulab/docprompting-conala` (`conala-docs.jsonl`) @ `48df7abf0f64f9279b4ee04386272eb9dc89ef89` | 62 MB | مصدر الاسترجاع الذي يستخدمه `create/odex.py` |
| 5 | النموذج `Qwen/Qwen2.5-Coder-0.5B` (base، safetensors، Apache-2.0) @ `8123ea2e9354afb7ffcc6c8641d1b2f5ecf18301` | 1.0 GB | مولّد محلي مجمّد وصغير يناسب 4 أنوية دون GPU. البديل الأبطأ: `Qwen2.5-Coder-1.5B` بحجم 3.1 GB |
| 6 | تنفيذ الكود المولَّد داخل `sandbox.py` الموصوف في القسم 5 | — | لا يوجد تقييم دون تنفيذ |

`deepseek-coder-1.3b-base` غير مقترح لأن أوزانه بصيغة `pytorch_model.bin` (pickle).

## 10) الخطوات الناقصة

- DS-1000 (القسم 4، البند 6) وRepoEval، وكلاهما خارج نطاق الـsmoke test.
- نموذج ثانٍ أقوى: بدونه لا يمكن الإجابة عن سؤال التكامل (القسم 12).
- لم أتحقق من مرجع PACE المذكور في `README_AR.md` (arXiv 2608.25115). لم أراجع الأدبيات، كما طُلب.

## 11) الحكم

- **Phase A:** READY.
- **Phase B (الـpipeline):** **READY**.
  - الـpipeline يعمل من أوله إلى آخره على بيانات حقيقية، بالمقيِّم الرسمي داخل الـSandbox، ومع ضابط إيجابي ناجح 23/23.
  - كل مهمة لها كل الحالات المسموحة وبـ5 عينات لكل حالة، ولا توجد حالات متخطاة.
- **السؤال العلمي (التكامل بين الأدلة):** **BLOCKED** بسبب floor effect.
  - النموذج المجمَّد لم ينجح في أي عينة، فكل المؤشرات صفر.
  - هذه النتيجة **لا تقول شيئاً** عن وجود التكامل أو غيابه.
  - المطلوب: موافقة على مولّد أقوى (القسم 12.5).

## 12) نتائج Phase B

### 12.1 الإصدارات المثبتة

| المكوّن | الإصدار / البصمة |
|---|---|
| CodeRAG-Bench | `f9e100ca9ed94b8f1983b356ae81966e30210cf4` (غير معدَّل، ويُتحقق منه وقت التشغيل) |
| ODEX `en_test.jsonl` | `neulab/odex@c3741a66c486b1a23beefdf6c75b06dba288d4f9`، sha256 `65af42b0…a095be`، 439 سجلاً |
| Corpus | `neulab/docprompting-conala@48df7abf0f64f9279b4ee04386272eb9dc89ef89` (`conala-docs.jsonl`)، sha256 `1df45601…a563d0`، 34003 وثيقة |
| الفهرس | BM25Okapi (`rank_bm25==0.2.2`، k1=1.5، b=0.75، ε=0.25)، `index_fingerprint=f5ffa8485d5251dc75bece53a21ac74ef2a09fe7e12c31cbb3c713ab5f199968` |
| النموذج | `Qwen/Qwen2.5-Coder-0.5B@8123ea2e9354afb7ffcc6c8641d1b2f5ecf18301`، sha256 لملف `model.safetensors` = `aff8914e…f80` (مطابق لـHF LFS)، fp32، CPU، 4 threads |
| البيئة | CPython 3.10.20 عبر uv في `/srv/crag/venv`: torch 2.3.1+cpu، transformers 4.40.0، datasets 2.19.2، numpy 1.26.4 (القائمة الكاملة في `env_freeze_venv310.txt`) |
| التوليد | `do_sample=True`، `T=0.2`، `top_p=0.95`، `top_k=0`، `max_new_tokens=256`؛ `sample_id` من 0 إلى 4، و`seed=sample_id` |
| التقييم | `compute_code_eval` الرسمي، بمهلة 3.0 ثوانٍ لكل برنامج، داخل `sandbox.py` (الـself-test ينجح عند بداية كل تشغيل) |

### 12.2 المهام (القاعدة في القسم 7)

| task_id | intent | group |
|---|---|---|
| 10_26153795 | Format a datetime string `when` to extract date only | datetime |
| 21_2195340 | split string 'Words, words, words.' using a regex '(\W+)' | re |
| 27_15405636 | argparse add argument with flag '--version' … | argparse |
| 38_1592158 | convert hex string '470FC614' to a float number | struct |
| 48_20573459 | get the date 7 days before the current date | datetime |
| 51_23164058 | encode binary string 'your string' to base64 code | base64 |
| 55_11236006 | identify duplicate values in list `mylist` | collections |
| 64_4172131 | create a random list of integers | random |

- استُبعدت 3 مهام سابقة بالترتيب (`15_29784889` و`32_40133826` و`74_17238587`) لأن الفحص المرجعي فشل فيها بخطأ `inconsistent use of tabs and spaces`.
  - السبب: المستودع يحوّل الـtab في سطر الدالة إلى 4 مسافات، بينما الحل المرجعي متعدد الأسطر يحتوي tabs.
  - الأثر محصور في بناء البرنامج المرجعي، وليس له علاقة بالنموذج. التفاصيل في `selected_tasks_selection_report.json`.

### 12.3 الحالات والعينات

- `prepare_manifest.py --topn 5 --max-docs 2 --budget 4096` أنتج **123 حالة** (لكل مهمة 16 حالة، عدا المهمة 27 التي لها 11).
  - في المهمة 27 الوثيقة r1 (`python.library.argparse`) طولها 15924 توكناً، أي أكبر من الميزانية، فاستُبعدت كل الحالات التي تضمها.
  - Top-k لهذه المهمة هو `r2+r3`.
- النتيجة: **615 سجلاً في `results.jsonl`** (123 × 5)، و`skipped.jsonl` فارغ، ولا توجد أخطاء توليد أو تقييم.
- عدد التوكنات الفعلي للسياق (التعليمة + الفواصل + الوثائق) يزيد عن مجموع الـmanifest بـ11–12 توكناً. أقصى سياق فعلي 2941 توكناً، وهو أقل من 4096، ولم يُقتطع شيء.
- طول الـprompt بالتوكنات: أدنى 26، والوسيط 619، والأقصى 2988.
- كل الـprompts تمر بـround-trip دقيق عبر الـtokenizer.
- زمن التوليد: المجموع 6708 ثانية، والوسيط 5.29 ثانية، والأقصى 50.2 ثانية.
- سبب التوقف: `stop_word` في 499 عينة، و`max_new_tokens` في 116 عينة.

### 12.4 النتيجة

- **passed = 0 / 615.** كل الحالات فاشلة في كل المهام.
- أمثلة على أسباب الفشل الحقيقية (من `eval_result`):
  - إرجاع أرقام تعكس معرّف الدالة (`return 1592158.0`).
  - `name 'np' is not defined` و`name 'pd' is not defined`، أي استخدام مكتبات دون استيرادها.
  - `'str' object has no attribute 'strftime'`.
  - أخطاء صياغة.
- **ضابط إيجابي:**
  - الـprompt الرسمي + الحل المرجعي، عبر نفس `postprocess_generation` ونفس المقيِّم في نفس الـSandbox: **23/23 passed** (`run_out/positive_control.json`).
  - إذن الصفر نتيجة حقيقية للنموذج، وليس خللاً في الـpipeline.
- `analyze_pilot.py --min-samples 5`: 8/8 مسائل مكتملة، و0 ناقصة. كل المؤشرات تساوي 0.000 (Swing وOracle Headroom والتفاعل وEmpirical Greedy).
  - هذا **floor effect** وليس دليلاً على غياب التكامل.
  - Empirical Greedy هنا تشخيص استرجاعي، **وليس PACE**.
- **قابلية التكرار:** عينة `10_26153795|none|0` أعطت نفس النص حرفياً في تشغيلين منفصلين (smoke وfull)، بنفس الـprompt والـseed، على CPU.
  - هذا لا يعني أن الـseeds نفسها تعطي مسارات متطابقة عبر prompts مختلفة.
  - في 17 من 123 حالة كانت البرامج الخمسة متطابقة، بسبب `T=0.2`.

### 12.5 المقترح التالي (لم يُنفَّذ؛ يحتاج موافقة)

- إعادة التشغيل بمولّد أقوى، مثل `Qwen/Qwen2.5-Coder-1.5B` (3.1 GB، revision `df3ce67c…`)، على نفس الـmanifest ونفس الـsample IDs.
- الكود يدعم الاستئناف، ويكفي `--out-dir` جديد.
- زمن التوليد سيزيد. لم أقِسه بعد، ويجب قياسه أولاً بـ`--only-subsets none --limit-tasks 1`.
- بدون GPU، النماذج من 7B فما فوق غير عملية هنا.

### 12.6 الأوامر المنفذة فعلاً (Phase B)

```bash
UV_PYTHON_INSTALL_DIR=/srv/crag/python uv python install 3.10.20 && uv venv --python 3.10.20 /srv/crag/venv
uv pip install --python /srv/crag/venv/bin/python --index-url https://download.pytorch.org/whl/cpu "torch==2.3.1+cpu"
uv pip install --python /srv/crag/venv/bin/python transformers==4.40.0 datasets==2.19.2 numpy==1.26.4 rank_bm25==0.2.2 accelerate==0.30.1 tqdm "fsspec<=2024.3.1"
curl -L .../datasets/neulab/odex/resolve/c3741a6.../en_test.jsonl ; .../neulab/docprompting-conala/resolve/48df7ab.../conala-docs.jsonl
curl -L .../Qwen/Qwen2.5-Coder-0.5B/resolve/8123ea2e.../{config.json,generation_config.json,model.safetensors,tokenizer*.json,vocab.json,merges.txt,LICENSE}
export CRAG_UPSTREAM=<code-rag-bench checkout>; PY=/srv/crag/venv/bin/python; M=/srv/crag/models/Qwen2.5-Coder-0.5B
$PY test_adapters.py                                   # 12 tests OK (بما فيها upstream GeneralODEX)
$PY select_tasks.py --odex /srv/crag/data/odex_en_test.jsonl --canonical $CRAG_UPSTREAM/retrieval/datasets/canonical/odex_docs.json --n 8 --verify-references --python $PY --upstream $CRAG_UPSTREAM --out selected_tasks.json
$PY retrieve_bm25.py --odex /srv/crag/data/odex_en_test.jsonl --corpus /srv/crag/data/conala-docs.jsonl --tasks selected_tasks.json --topn 5 --out retrieval.jsonl
$PY normalize_candidates.py --retrieval retrieval.jsonl --model-dir $M --out candidates.jsonl
python prepare_manifest.py --candidates candidates.jsonl --out manifest.jsonl --topn 5 --max-docs 2 --budget 4096
$PY run_manifest.py ... --out-dir run_smoke_none --samples 1 --only-subsets none --limit-tasks 1   # smoke بدون استرجاع
$PY run_manifest.py --manifest manifest.jsonl --candidates candidates.jsonl --odex /srv/crag/data/odex_en_test.jsonl --model-dir $M --model-id Qwen/Qwen2.5-Coder-0.5B --model-revision 8123ea2e9354afb7ffcc6c8641d1b2f5ecf18301 --upstream $CRAG_UPSTREAM --sandbox-python $PY --out-dir run_out --samples 5 --threads 4
cp run_out/results.jsonl results.jsonl
python analyze_pilot.py --manifest manifest.jsonl --results results.jsonl --out real_report --min-samples 5
$PY positive_control.py --run-dir run_out --upstream $CRAG_UPSTREAM --sandbox-python $PY   # 23/23
```

### 12.7 ملفات الخرج

- `candidates.jsonl` و`manifest.jsonl` و`results.jsonl`: الخرج الرسمي للـpilot.
- `retrieval.jsonl` و`selected_tasks*.json`: مدخلات الاسترجاع واختيار المهام.
- `real_report/{REPORT_AR.md,analysis.json}`: خرج `analyze_pilot.py`.
- `run_out/`:
  - `run_config.json`: الإعدادات وبصمات الملفات ونتيجة الـsandbox self-test.
  - `rag_inputs.jsonl`: المدخلات بصيغة المستودع الرسمي.
  - `raw/generations.jsonl`: الـprompt والنص الخام والبرنامج.
  - `raw/evaluations.jsonl` و`raw/eval_logs.jsonl`.
  - `positive_control.json`.
- `run_smoke_none/`: تشغيل الـsmoke.
