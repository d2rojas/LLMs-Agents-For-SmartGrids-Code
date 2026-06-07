# LaTeX Integration Guide for GridDebugAgent Section

## Overview
This guide explains how to integrate GridDebugAgent content into your main paper's Section V.E.

---

## Files You Need

### Main Section File
- **`section_v_e.tex`** - Complete Section V.E content (compact, ~1 page with figure)

### Supporting Figures
- **`griddebug_trajectory.tex`** - Trajectory figure (automatically included via `\input{}` in section_v_e.tex)
- **`griddebug_architecture.tex`** - Architecture diagram (optional, can be placed earlier in Section V)

---

## Integration Steps

### Option 1: Direct Inclusion (Recommended)

In your main paper file, where Section V.E should appear:

```latex
% In your main paper .tex file

\section{Case Studies and Applications}  % or whatever Section V is

% ... Section V.A, V.B, V.C, V.D ...

% Section V.E: GridDebugAgent
\input{section_v_e.tex}

% Continue with Section V.F, etc.
```

**Important:** Make sure the following files are in the same directory as your main .tex file:
- `section_v_e.tex`
- `griddebug_trajectory.tex`

Or adjust paths accordingly (e.g., `\input{docs/section_v_e.tex}`).

---

### Option 2: Copy-Paste

If you prefer not to use `\input{}`:

1. Open `section_v_e.tex`
2. Copy the entire content
3. Paste it directly into your main paper at Section V.E
4. Make sure `griddebug_trajectory.tex` is available for the nested `\input{griddebug_trajectory.tex}` call

---

## Architecture Figure Placement

The architecture diagram (`griddebug_architecture.tex`) is **not included** in the compact section to save space. You have two options:

### Option A: Place it in Section V introduction
```latex
\section{Case Studies and Applications}

Recent advances in LLM-based agents enable complex reasoning over specialized domains...

\input{griddebug_architecture.tex}  % Place architecture here

\subsection{First Case Study}
% ...

\subsection{GridDebugAgent...}
\input{section_v_e.tex}
```

### Option B: Place it within Section V.E
Uncomment the lines at the bottom of `section_v_e.tex`:
```latex
% Optional: Insert architecture figure if space permits
\begin{figure*}[t]
\input{griddebug_architecture.tex}
\end{figure*}
```

**Note:** This will make Section V.E longer than 1 page. Use `figure*` for two-column spanning.

---

## Required LaTeX Packages

Ensure your preamble includes:

```latex
% For the trajectory figure
\usepackage{xcolor}  % if not already included

% For the architecture diagram (if using it)
\usepackage{tikz}
\usetikzlibrary{positioning, shapes, arrows, calc}

% For tables
\usepackage{booktabs}  % for \toprule, \midrule, \bottomrule

% For figures
\usepackage{graphicx}
```

### Custom Commands Used in Trajectory

The trajectory figure uses these highlighting commands (should match your paper's style):
- `\rolehl{}`
- `\contexthl{}`
- `\retrievedhl{}`
- `\reasonhl{}`
- `\outputhl{}`
- `\goodmark` (checkmark symbol)

**If these are not defined in your main paper**, add these definitions to your preamble:

```latex
% Define highlighting commands for trajectory figure
\newcommand{\rolehl}[1]{\textcolor{blue!80!black}{\textbf{#1}}}
\newcommand{\contexthl}[1]{\textcolor{teal!70!black}{#1}}
\newcommand{\retrievedhl}[1]{\textcolor{purple!70!black}{#1}}
\newcommand{\reasonhl}[1]{\textcolor{orange!80!black}{\textit{#1}}}
\newcommand{\outputhl}[1]{\textcolor{green!60!black}{#1}}
\newcommand{\goodmark}{\textcolor{green!70!black}{\checkmark}}

% Define promptfigure environment (if not already defined)
\usepackage{mdframed}
\newenvironment{promptfigure}[1]{%
  \begin{mdframed}[linewidth=1pt, linecolor=gray!30, backgroundcolor=gray!5]
  \textbf{#1}
  \par\vspace{2mm}
}{%
  \end{mdframed}
}
```

**Or**, if your paper already defines these commands differently, adjust the trajectory file accordingly.

---

## Citations Referenced

The section references these citations (add to your .bib file if missing):

```bibtex
@article{yao2023react,
  title={ReAct: Synergizing reasoning and acting in language models},
  author={Yao, Shunyu and Zhao, Jeffrey and Yu, Dian and others},
  journal={arXiv preprint arXiv:2210.03629},
  year={2023}
}

@article{thurner2018pandapower,
  title={pandapower—an open-source python tool for convenient modeling, analysis, and optimization of electric power systems},
  author={Thurner, Leon and Scheidler, Alexander and Sch{\"a}fer, Florian and others},
  journal={IEEE Transactions on Power Systems},
  volume={33},
  number={6},
  pages={6510--6521},
  year={2018}
}
```

Add citation for GPT-4o if not already in your references.

---

## Figure and Table Labels

The section uses these labels for cross-referencing:

- `\label{fig:griddebug_architecture}` - Architecture diagram
- `\label{fig:griddebug_trajectory}` - Trajectory figure
- `\label{tab:griddebug_results}` - Results table

Reference them in text:
```latex
As shown in Figure~\ref{fig:griddebug_trajectory}, the agent...
Table~\ref{tab:griddebug_results} presents repair performance...
```

---

## Space Optimization Tips

If you need to save more space:

### 1. Shrink the table
```latex
\begin{table}[ht]
\centering
\caption{...}
\label{tab:griddebug_results}
\footnotesize  % or \scriptsize for even smaller
\begin{tabular}{...}
...
\end{tabular}
\end{table}
```

### 2. Make trajectory figure smaller
Edit `griddebug_trajectory.tex`, change line 3:
```latex
\begin{minipage}{0.94\linewidth}  % Change to 0.85 or 0.75
```

And adjust font sizes in line 5:
```latex
{\ttfamily\scriptsize  % Change from \small to \scriptsize
```

### 3. Reduce paragraph spacing
Add before the section:
```latex
\setlength{\parskip}{0pt}
```

### 4. Use compact list style
If you convert any content to lists, use:
```latex
\usepackage{enumitem}
\begin{itemize}[noitemsep,topsep=0pt]
  \item ...
\end{itemize}
```

---

## Verification Checklist

Before compiling:

- [ ] `section_v_e.tex` is in the correct directory
- [ ] `griddebug_trajectory.tex` is in the correct directory (or path is adjusted)
- [ ] All required packages are in preamble
- [ ] Custom commands (`\rolehl`, etc.) are defined
- [ ] `promptfigure` environment is defined
- [ ] Citations are in .bib file
- [ ] Compile twice to resolve references

---

## Expected Output

When compiled, Section V.E should:
- Fit on approximately 1 page (with figure)
- Include a results table (Table with 4 rows)
- Include the trajectory figure showing 2-round ReAct loop
- Have 4 paragraphs: Problem Setup, System Architecture, Evaluation, Results, Discussion
- All cross-references resolve correctly

---

## Troubleshooting

### Error: `promptfigure` environment undefined
**Fix:** Add the environment definition to your preamble (see "Custom Commands" section above)

### Error: `\rolehl` undefined
**Fix:** Add highlight command definitions to preamble

### Error: Cannot find file `griddebug_trajectory.tex`
**Fix:**
- Check file is in same directory as main .tex file
- Or adjust path: `\input{docs/griddebug_trajectory.tex}`

### Table looks too wide
**Fix:** Use `\small` or `\footnotesize` before `\begin{tabular}`

### Figure placement issues
**Fix:**
- Use `[ht]` for here/top placement
- Use `[t]` for top-of-page only
- Use `figure*` for two-column spanning
- Add `\clearpage` before section if needed

### Section exceeds 1 page
**Fix:**
- Remove architecture figure (or place elsewhere)
- Reduce trajectory figure size (see space optimization tips)
- Shorten Discussion paragraph
- Use smaller fonts for table

---

## Quick Test

To quickly test if everything works:

1. Create a minimal test file:
```latex
\documentclass{IEEEtran}  % or your paper's class
\usepackage{booktabs}
\usepackage{xcolor}
\usepackage{tikz}
\usetikzlibrary{positioning, shapes, arrows, calc}

% Add custom commands here
\newcommand{\rolehl}[1]{\textcolor{blue!80!black}{\textbf{#1}}}
% ... (add all other commands)

\begin{document}

\section{Test Section}
\input{section_v_e.tex}

\end{document}
```

2. Compile and check for errors
3. If successful, integrate into main paper

---

## Contact / Questions

If you encounter issues:
1. Check that all files are in the correct location
2. Verify all required packages are loaded
3. Check custom commands are defined
4. Review error messages for missing files/commands

The section is designed to be self-contained and compact. Adjust as needed for your paper's style and space constraints.
