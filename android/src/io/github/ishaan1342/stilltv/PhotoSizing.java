package io.github.ishaan1342.stilltv;

/** Power-of-two decoding sized for the actual surface and a per-bitmap memory budget. */
final class PhotoSizing {
    static int sample(int width, int height, int target, long maxBytes) {
        if (width <= 0 || height <= 0 || target <= 0 || maxBytes < 4)
            throw new IllegalArgumentException("Invalid photo bounds");
        int sample = 1;
        while (Math.max(width, height) / (sample * 2) >= target) sample *= 2;
        while (((width + (long)sample - 1) / sample) *
                ((height + (long)sample - 1) / sample) * 4 > maxBytes) sample *= 2;
        return sample;
    }
}
