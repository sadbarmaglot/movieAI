import aiohttp
import asyncio
import numpy as np

from io import BytesIO
from PIL import Image
from typing import Optional, Tuple
from sklearn.cluster import KMeans
from google.cloud import storage
from settings import BUCKET_NAME


class GoogleCloudClient:
    def __init__(self, bucket_name: str = BUCKET_NAME):
        self.bucket_name = bucket_name
        self.storage_client = storage.Client()
        self.bucket = self.storage_client.bucket(bucket_name)

    def _poster_exists_sync(self, file_name: str) -> bool:
        blob = self.bucket.blob(file_name)
        return blob.exists()

    async def poster_exists(self, file_name: str) -> bool:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._poster_exists_sync, file_name)

    @staticmethod
    def _compute_background_color(image_data: bytes, k: int = 4, resize: int = 150) -> str:
        img = Image.open(BytesIO(image_data)).convert("RGB")
        img = img.resize((resize, resize))
        img_np = np.array(img).reshape(-1, 3)

        kmeans = KMeans(n_clusters=k, random_state=42)
        kmeans.fit(img_np)

        dominant_color = kmeans.cluster_centers_[np.argmax(np.bincount(kmeans.labels_))]
        return 'linear-gradient(to bottom, #{:02x}{:02x}{:02x}, #1c1c1c);'.format(*map(int, dominant_color))

    async def download_and_upload_poster(
        self,
        poster_url: str,
        source: str = "kp"
    ) -> Tuple[Optional[str], Optional[str]]:
        file_name = self._build_file_name(poster_url, source)
        file_path = f"https://storage.googleapis.com/{self.bucket_name}/{file_name}"

        if await self.poster_exists(file_name):
            return file_path, None

        async with aiohttp.ClientSession() as session:
            async with session.get(poster_url) as response:
                if response.status == 200:
                    content = await response.read()
                    background_color = self._compute_background_color(content)

                    blob = self.bucket.blob(file_name)
                    blob.upload_from_string(content, content_type="image/jpeg")
                    return file_path, background_color
                else:
                    print(f"Ошибка загрузки {poster_url}: {response.status}")
                    return None, None

    @staticmethod
    def _build_file_name(poster_url: str, source: str) -> str:
        if source == "tmdb":
            return f"tmdb_{poster_url.split('/')[-1]}"
        elif source == "kp":
            return "kp_" + "_".join(poster_url.split("/")[-3:-1])
        else:
            raise ValueError("Unsupported source type for poster filename.")
