import os


class TestVectorReader:
    """Helper class to read test vector files"""

    @staticmethod
    def read_hex_file(filename):
        """Read a file with hex values, one per line"""
        vectors = []
        try:
            with open(filename, "r") as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if line and not line.startswith(
                        "#"
                    ):  # Skip empty lines and comments
                        try:
                            # Convert hex string to bytes
                            data = bytes.fromhex(line)
                            vectors.append(data)
                        except ValueError as e:
                            print(
                                f"Warning: Invalid hex on line {line_num}: {line[:20]}..."
                            )
                            print(f"Error: {e}")

            print(f"Loaded {len(vectors)} test vectors from {filename}")
            return vectors

        except FileNotFoundError:
            print(f"Error: File '{filename}' not found")
            return []
        except Exception as e:
            print(f"Error reading file '{filename}': {e}")
            return []

    @staticmethod
    def load_dilithium_vectors(base_path, sec_level, vector_index=0):
        """Load all Dilithium test vectors for a specific test case"""
        vectors = {}

        # Define the files for each component
        files = {
            "rho": os.path.join(base_path, "shared", "rho.txt"),
            "msg": os.path.join(base_path, "shared", "msg.txt"),
            "msg_len": os.path.join(base_path, "shared", "msg_len.txt"),
            "c": os.path.join(base_path, str(sec_level), "c.txt"),
            "z": os.path.join(base_path, str(sec_level), "z.txt"),
            "t1": os.path.join(base_path, str(sec_level), "t1.txt"),
            "h": os.path.join(base_path, str(sec_level), "h.txt"),
        }

        # Load each component
        for component, filename in files.items():
            data = TestVectorReader.read_hex_file(filename)
            vectors[component] = data[vector_index]
            print(f"Loaded {component}: {len(vectors[component])} bytes")

        return vectors


if __name__ == "__main__":
    kat_loader = TestVectorReader()
    kat_path = os.path.join(os.getcwd(), "test", "KAT")
    a = kat_loader.load_dilithium_vectors(base_path=kat_path, sec_level=2)
    print(a["rho"])
