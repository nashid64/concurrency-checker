import java.util.concurrent.atomic.AtomicInteger;

public class SafeDemo {
    private static final AtomicInteger counter = new AtomicInteger();
    private static final Object lockA = new Object();
    private static final Object lockB = new Object();

    static void work() {
        for (int i = 0; i < 1000; i++) {
            counter.incrementAndGet();
        }
        synchronized (lockA) {
            synchronized (lockB) {
                System.out.println("ordered locks");
            }
        }
    }

    public static void main(String[] args) throws Exception {
        Thread t1 = new Thread(SafeDemo::work);
        Thread t2 = new Thread(SafeDemo::work);
        t1.start(); t2.start();
        t1.join(); t2.join();
        System.out.println(counter.get());
    }
}
