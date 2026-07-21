---
id: windows-in-the-ci-matrix
board: code
section: compat
status: shipped
category: Compat · Platform
complexity: S
impact: High
wow: 4
note: untested OS
order: 1
owner: loop/windows-ci-matrix
pr: 177
title: Windows in the CI matrix
---
The test matrix runs macOS and Ubuntu only, so
           <code>windows-latest</code> path separators, case-sensitivity and
           console-encoding bugs ship uncaught to any Windows user. Adding one
           matrix leg closes the biggest untested surface for a tool that promises
           to work "everywhere your agent does".
