public class RaceDemo {
    private static int counter = 0;

    static void work() {
        for (int i = 0; i < 1000; i++) {
            counter++;
        }
    }

    public static void main(String[] args) throws Exception {
        Thread t1 = new Thread(RaceDemo::work);
        Thread t2 = new Thread(RaceDemo::work);
        t1.start(); t2.start();
        t1.join(); t2.join();
        System.out.println(counter);
    }
}
