# تقرير المرحلتين A وB — ربط أداة الأدلة بـ CodeRAG-Bench

**الحالة:** Phase A مكتملة. Phase B **BLOCKED** حتى تتم الموافقة على التنزيلات والتثبيت وتنفيذ الكود المولَّد داخل الـSandbox (القسم 9).
**لا توجد أي نتائج pass/fail لنموذج حتى الآن.** كل ما يرد أدناه فحوص بنية تحتية، أو تشغيل لحلول مرجعية من benchmark داخل الـSandbox.

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
| `test_adapters.py` | 12 اختباراً offline (2 منها تتخطى الآن لغياب torch/datasets) |

الملفات الأصلية للـpilot (`prepare_manifest.py` و`analyze_pilot.py` و`test_pilot.py`) **لم تُعدَّل**.

## 7) خطة Phase B المقترحة (لم تُنفَّذ)

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

## 9) الموافقات المطلوبة

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

- Phase B بكاملها.
- DS-1000 (القسم 4، البند 6) وRepoEval، وكلاهما خارج نطاق الـsmoke test.
- لم أتحقق من مرجع PACE المذكور في `README_AR.md` (arXiv 2608.25115). لم أراجع الأدبيات، كما طُلب.

## 11) الحكم

- **Phase A:** READY. البنية والـadapter والـSandbox مفحوصة.
- **Phase B:** **BLOCKED**، بانتظار الموافقة على البنود 1–6 في القسم 9.
