#!/bin/bash

echo "========================================"
echo " Docker Environment Version Check"
echo "========================================"

echo "[OS]"
if [ -f /etc/os-release ]; then
    grep PRETTY_NAME /etc/os-release | cut -d'"' -f2
else
    echo "Unknown OS"
fi
echo ""

echo "[Core Tools & Python]"
if command -v python3 &> /dev/null; then python3 --version; else echo "python3 not found"; fi
if command -v pip &> /dev/null; then pip --version | awk '{print "pip " $2 " (python " $6 ")"}'; else echo "pip not found"; fi
if command -v git &> /dev/null; then git --version; else echo "git not found"; fi

echo ""
echo "[Clang & LLVM]"
if command -v clang &> /dev/null; then clang --version | head -n 1; else echo "clang not found"; fi
if command -v clang-format &> /dev/null; then clang-format --version; else echo "clang-format not found"; fi

echo ""
echo "[Static Analysis Tools]"
if command -v cloc &> /dev/null; then
    echo "cloc version $(cloc --version)"
else
    echo "cloc not found"
fi

if command -v pmd &> /dev/null; then
    # PMD 7.x 系は --version でバージョンを出力します
    pmd --version
else
    echo "PMD not found"
fi

echo "========================================"