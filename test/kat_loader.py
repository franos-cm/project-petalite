import os
from typing import List, Dict


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
    def load_dilithium_vectors(
        base_path, sec_level, initial_vec_index=0, vec_num=1
    ) -> Dict[int, Dict[str, List[bytes]]]:
        """Load all Dilithium test vectors for a specific test case"""
        vectors = {
            i: dict() for i in range(initial_vec_index, initial_vec_index + vec_num)
        }

        # Define the files for each component
        files = {
            "k": os.path.join(base_path, "shared", "k.txt"),
            "msg_len": os.path.join(base_path, "shared", "msg_len.txt"),
            "msg": os.path.join(base_path, "shared", "msg.txt"),
            "rho": os.path.join(base_path, "shared", "rho.txt"),
            "seed": os.path.join(base_path, "shared", "seed.txt"),
            "c": os.path.join(base_path, str(sec_level), "c.txt"),
            "h": os.path.join(base_path, str(sec_level), "h.txt"),
            "s1": os.path.join(base_path, str(sec_level), "s1.txt"),
            "s2": os.path.join(base_path, str(sec_level), "s2.txt"),
            "t0": os.path.join(base_path, str(sec_level), "t0.txt"),
            "t1": os.path.join(base_path, str(sec_level), "t1.txt"),
            "tr": os.path.join(base_path, str(sec_level), "tr.txt"),
            "z": os.path.join(base_path, str(sec_level), "z.txt"),
        }

        # Load each component
        for component, filename in files.items():
            data = TestVectorReader.read_hex_file(filename)
            for index, vals in vectors.items():
                vals[component] = data[index]
            print(
                f"Loaded {component} for vectors {initial_vec_index} to {initial_vec_index+vec_num}"
            )

        return vectors


if __name__ == "__main__":
    kat_loader = TestVectorReader()
    kat_path = os.path.join(os.getcwd(), "test", "KAT")
    a = kat_loader.load_dilithium_vectors(base_path=kat_path, sec_level=2)
    print(a["rho"])
