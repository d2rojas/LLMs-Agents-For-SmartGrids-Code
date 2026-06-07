# Quick Questions for Student Team

## 🔴 URGENT - Security

**API Key in `.env` file:**
- Your OpenAI API key is visible in `backend/.env`
- **Action:** Revoke this key immediately in your OpenAI account
- Generate a new key and update locally
- Create `.env.example` template for others

---

## 📝 For the Paper

### 1. Credits & Attribution
- **Student names** (for acknowledgments or co-authorship)?
- **Institution/Course** (e.g., "University X, CSE 599")?
- **GitHub repository** - will code be public? URL?

### 2. Model Used
- Code shows **GPT-4o** (not GPT-4)
- Confirm this is correct for the paper citation

### 3. Minor Documentation Fixes
- **README.md** says 10 tools → actually 23 tools (update?)
- **README.md** missing Grid Actions category (4 repair tools)
- **Voltage limits:** Paper should use 0.95-1.05 p.u. (not 1.06)

---

## ❓ Optional (Nice to Have)

### 4. Hyperparameters
- Why **temp=0.3**? (was this tuned or standard for tool-calling?)
- Why **max_iter=10**? (tried other values?)

### 5. Tool Usage
- Which tools are used most frequently?
- Can you extract this from your JSON logs?

---

## ✅ Already Well-Documented

Great job on these:
- ✅ All 39 scenarios documented with results
- ✅ Baseline evaluation completed
- ✅ Latency statistics detailed by network
- ✅ Failure analysis provided
- ✅ Complete evaluation results in JSON

---

## Response Format

Please reply with:

1. **Security:** ☐ API key revoked (done/in progress)
2. **Credits:** Names, affiliation, GitHub URL (if public)
3. **Model:** Confirm GPT-4o is correct
4. **Docs:** Will update README? (yes/no)
5. **Optional:** Hyperparameter rationale / tool usage stats (if available)

Thank you! 🚀
