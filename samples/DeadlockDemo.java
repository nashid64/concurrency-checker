public class DeadlockDemo {
    private static final Object lockA = new Object();
    private static final Object lockB = new Object();

    static void first() {
        synchronized (lockA) {
            sleep(50);
            synchronized (lockB) {
                System.out.println("first");
            }
        }
    }

    static void second() {
        synchronized (lockB) {
            sleep(50);
            synchronized (lockA) {
                System.out.println("second");
            }
        }
    }

    static void sleep(long ms) {
        try { Thread.sleep(ms); } catch (InterruptedException e) { Thread.currentThread().interrupt(); }
    }

    public static void main(String[] args) throws Exception {
        Thread t1 = new Thread(DeadlockDemo::first);
        Thread t2 = new Thread(DeadlockDemo::second);
        t1.start(); t2.start();
        t1.join(); t2.join();
    }
}
