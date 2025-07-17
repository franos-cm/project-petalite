from litex import RemoteClient

wb = RemoteClient(csr_csv="./build-soc/host/csr.csv")
wb.open()
# get identifier
fpga_id = ""
print("identifier_mem: ")
for i in range(256):
    c = chr(wb.read(wb.bases.identifier_mem + 4 * i) & 0xFF)
    fpga_id += c
    if c == "\0":
        break
print("fpga_id: " + fpga_id)
wb.close()
