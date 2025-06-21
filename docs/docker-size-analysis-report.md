# Docker Image Size Analysis Report

## Facts

**Image Size**: 1.75GB total (1.63GB added to 115MB base)

### Space Usage Breakdown
```
PyTorch:      694MB (40% of additions)
spaCy:        124MB
scipy:        116MB
transformers: 102MB
sympy:         74MB
sklearn:       56MB
```

### Key Files
```
libtorch_cpu.so: 399MB (single file)
Total packages:   1.6GB
Application code: 92MB
```

### Data Volume (Healthy)
```
Actual usage: 11MB
Qdrant data:  7.1MB (248 records)
SQLite DB:    3.1MB
```

**Note**: Qdrant shows 2.97GB "apparent size" due to memory-mapped files - normal behavior.

### Runtime Resources
```
heimdall-mcp: 532MB RAM
qdrant:       220MB RAM
Total:        752MB RAM
```

## Root Cause

1. **Full PyTorch distribution** includes unnecessary CUDA support
2. **No build cleanup** - pip cache and bytecode remain
3. **Heavy ML stack** - complete scipy/numpy ecosystem

## Optimization Targets

### High Impact
- **PyTorch CPU-only**: Save 400-450MB
- **Remove sympy**: Save 74MB (if unused)
- **Build cleanup**: Save 50-100MB

### Medium Impact
- **Dependency review**: Save 100-200MB
- **Package minimization**: Save 50-150MB

## Recommendations

### Immediate (1-2 days)
```dockerfile
# Use CPU-only PyTorch
--extra-index-url https://download.pytorch.org/whl/cpu
torch==2.1.0+cpu

# Add cleanup
RUN pip cache purge && \
    find /usr/local -name "*.pyc" -delete && \
    find /usr/local -type d -name "__pycache__" -exec rm -rf {} +
```

### Target: **<1GB image** (from 1.75GB)
