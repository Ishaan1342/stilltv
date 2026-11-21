package io.github.ishaan1342.stilltv;

public final class PhotoSizingTest {
    private static void check(int width, int height, int surface, long budget, int expected) {
        int sample = PhotoSizing.sample(width, height, surface, budget);
        if (sample != expected) throw new AssertionError("Unexpected sample: " + sample);
        long bytes = ((width + (long)sample - 1) / sample) *
                ((height + (long)sample - 1) / sample) * 4;
        if (bytes > budget) throw new AssertionError("Decode exceeds budget");
    }
    public static void main(String[] args) {
        long mb = 1024L * 1024;
        check(3840, 2160, 3840, 32 * mb, 1); // Keep real 4K on a capable heap/surface.
        check(5760, 3240, 3840, 32 * mb, 2); // Avoid a 75 MB decode for a 4K view.
        check(7680, 4320, 3840, 32 * mb, 2);
        check(3840, 2160, 1920, 32 * mb, 2);
        check(3840, 2160, 3840, 16 * mb, 2); // Smaller heaps get a safe fallback.
        check(7680, 4320, 960, 8 * mb, 8);
        check(5761, 3241, 3840, 32 * mb, 2);
        try {
            PhotoSizing.sample(0, 2160, 3840, 32 * mb);
            throw new AssertionError("Invalid dimensions accepted");
        } catch (IllegalArgumentException expected) { }
        System.out.println("Photo decode sizing checks passed");
    }
}
