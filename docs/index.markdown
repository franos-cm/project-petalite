---
layout: default
title: Project Petalite
---

<head>
<link rel="shortcut icon" type="image/png" href="assets/favicon.ico">
</head>

<p align="center">
  <img src="{{ '/assets/images/petalite-logo.png' | relative_url }}" alt="Petalite logo" width="50%">
</p>

**Project Petalite** is a proof-of-concept for a hardware Trusted Platform Module (TPM) that implements post-quantum cryptography, specifically the CRYSTALS-Dilithium signature scheme.

This project was developed as an undergraduate thesis for the Computer Engineering degree at the Universidade de São Paulo (USP). As such, the thesis itself functions as the official specification for the project, explaining it in great detail.

Although post-quantum cryptography has started to become standardized — the most recent example being ML-KEM and ML-DSA, both based on the CRYSTALS suite — no such algorithm is currently a part of the official TPM specification. Therefore, investigating how those schemes could be integrated into a future version of the TPM is especially interesting.

The foundation of this project is the Petalite SoC, a single-core RISC-V SoC developed using LiteX. The architecture of the SoC is shown below.

<p align="center">
  <img src="{{ '/assets/images/petalite-architecture.png' | relative_url }}" alt="Petalite architecture." width="100%">
</p>

The SoC executes a modified version of the reference software TPM as its boot ROM. Moreover, the Dilithium algorithm is implemented as a hardware accelerator. This decreases both the latency of the algorithm, and the potential attack surface.

The project was synthesized in a NetFPGA-SUME development board using Vivado. A test suite was also developed, in which the new TPM commands developed for Dilithium were sent via UART, and the TPM produced the expected responses. Thus, the project was considered duely validated.

The cycle latency for each new (or modified) TPM command is shown in the table below, which also compares two alternative TPM designs: one using the reference software implementation of Dilithium, and the other leveraging the mentioned hardware accelerator. This specific comparison was made using the Dilithium parameter set III.


| **Implementation**     | **CreatePrimary** | **HashSign**    | **HashVerify** |
|------------------------|------------------:|----------------:|----------------:|
| **Reference software** | 14,738,219        | 107,385,854     | 11,891,749      |
| **Hardware accelerated** | 5,679,331       | 880,151         | 1,118,290       |
| **Speedup (%)**        | **259.5%**        | **12,200.8%**   | **1,063.4%**    |


## Relevant links

### Documentation

This section includes all the documents required for the undergraduate thesis:

- [Undergraduate thesis (project specification)]({{ '/assets/specs/petalite-specs.pdf' | relative_url }})

- [Press release (in Portuguese)]({{ '/assets/specs/press-release.pdf' | relative_url }})

- [Banner (in Portuguese)]({{ '/assets/specs/banner.pdf' | relative_url }})

### Components

For the sake of organization, this project was divided into several git repositories:

- [Repository for the SoC](https://github.com/franos-cm/project-petalite)
  
- [Repository for the firmware](https://github.com/franos-cm/pq-tpm)

- [Repository for the Dilithium accelerator](https://github.com/franos-cm/dilithium-rtl)

- [Repository for the SHAKE accelerator (part of the Dilithium accelerator)](https://github.com/franos-cm/shake-sv)

- [A Litex fork for building the project successfully](https://github.com/franos-cm/litex/tree/project-petalite)

### Miscellaneous

- [CRYSTALS suite](https://pq-crystals.org/)
  
- [TPM 2.0 Library](https://trustedcomputinggroup.org/resource/tpm-library-specification/)

- [NetFPGA SUME](https://netfpga.org/NetFPGA-SUME.html)


<hr>
<p style="text-align:center; opacity: 0.7; font-size: 0.9em;">
  Last updated: December 2025
</p>